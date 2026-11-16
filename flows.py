"""The conversation steps. Each function sends the customer's next message.

Booking is one loop: whatever the customer has chosen so far is kept in the session,
and advance() shows the dropdown for the first thing still missing
(service -> date -> time), then the Confirm buttons. Taps and typed requests both feed it.
"""
import logging

import handoff
import history
import menus
import schedule
import session
import sheets
import whatsapp

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- sending (with chat memory)

def _say(phone: str, text: str) -> None:
    whatsapp.send_text(phone, text)
    history.save_message(phone, "bot", text)


def _show(phone: str, menu: dict) -> None:
    whatsapp.send_menu(phone, menu)
    history.save_message(phone, "bot", "[menu] " + menu["body"].replace("\n", " ")[:150])


# ---------------------------------------------------------------- simple screens

def show_main_menu(phone: str, intro: str | None = None) -> None:
    _show(phone, menus.main_menu(intro))


def show_services(phone: str) -> None:
    _show(phone, menus.services_info(sheets.get_services()))


def show_info(phone: str) -> None:
    _show(phone, menus.salon_info())


# ---------------------------------------------------------------- booking

def _store(phone: str, **fields) -> None:
    """Save the fields that were actually provided (ignores None)."""
    provided = {k: v for k, v in fields.items() if v}
    if provided:
        session.set_session(phone, **provided)


def start_booking(phone: str, service=None, date=None, time=None, fresh: bool = False) -> None:
    """Begin or continue a booking with whatever the customer has already told us."""
    if fresh:
        session.clear_session(phone)
    _store(phone, service=service, date=date, time=time)
    advance(phone)


def show_slots(phone: str, date=None, service=None) -> None:
    """Customer asked what is free. With a date, jump straight to that day's time slots."""
    _store(phone, service=service, date=date)
    chosen = session.get_session(phone).get("date")
    if chosen and chosen in schedule.bookable_dates():
        _show_slots(phone, chosen)
    else:
        advance(phone)


def on_service(phone: str, service_id: str) -> None:
    _store(phone, service=service_id)
    advance(phone)


def on_date(phone: str, date: str) -> None:
    _store(phone, date=date)
    advance(phone)


def on_slot(phone: str, date: str, time: str) -> None:
    _store(phone, date=date, time=time)
    advance(phone)


def change_booking(phone: str) -> None:
    session.clear_session(phone)
    advance(phone, notice="No problem, let's start over.")


def has_pending_confirmation(phone: str) -> bool:
    """True when service, date and time are all chosen, i.e. the Confirm buttons are waiting."""
    draft = session.get_session(phone)
    return all(draft.get(key) for key in ("service", "date", "time"))


def _clean_draft(phone: str, services: list[dict]) -> dict:
    """Drop saved choices that are no longer valid (unknown service, date out of range)."""
    draft = session.get_session(phone)
    drop = {}
    if draft.get("service") and draft["service"] not in {s["id"] for s in services}:
        drop["service"] = None
    if draft.get("date") and draft["date"] not in schedule.bookable_dates():
        drop["date"] = None
        drop["time"] = None
    if drop:
        session.set_session(phone, **drop)
        draft = session.get_session(phone)
    return draft


def _show_slots(phone: str, date: str, notice: str | None = None) -> None:
    times = schedule.open_slots(date)
    if not times:
        session.set_session(phone, date=None, time=None)
        advance(phone, notice=f"{menus.fmt_date(date)} is fully booked. Please pick another day.")
        return
    _show(phone, menus.slots_menu(date, times, intro=notice))


def advance(phone: str, notice: str | None = None) -> None:
    """Show the next thing the booking needs."""
    services = sheets.get_services()
    draft = _clean_draft(phone, services)

    if not draft.get("service"):
        return _show(phone, menus.services_menu(services, intro=notice))
    if not draft.get("date"):
        return _show(phone, menus.dates_menu(schedule.bookable_dates(), schedule.today_str(), intro=notice))

    if draft.get("time") and draft["time"] not in schedule.open_slots(draft["date"]):
        notice = notice or f"Sorry, {menus.fmt_time(draft['time'])} on {menus.fmt_date(draft['date'])} isn't available."
        session.set_session(phone, time=None)
        draft.pop("time")
    if not draft.get("time"):
        return _show_slots(phone, draft["date"], notice)

    service = next(s for s in services if s["id"] == draft["service"])
    _show(phone, menus.confirm_buttons(service, draft["date"], draft["time"]))


def confirm(phone: str, name: str) -> None:
    """Customer tapped Confirm: write the booking to the sheet."""
    if not has_pending_confirmation(phone):
        return advance(phone)
    services = sheets.get_services()
    draft = _clean_draft(phone, services)
    service = next((s for s in services if s["id"] == draft.get("service")), None)
    if not (service and draft.get("date") and draft.get("time")):
        return advance(phone)

    booking = None
    if draft["time"] in schedule.open_slots(draft["date"]):
        booking = sheets.add_booking(phone, name, service, draft["date"], draft["time"])
    if booking is None:
        session.set_session(phone, time=None)
        return advance(phone, notice="Sorry, that slot was just taken.")

    session.clear_session(phone)
    _show(phone, menus.booking_card(booking, "✅ Booking confirmed! See you soon."))


# ---------------------------------------------------------------- check / cancel

def show_my_bookings(phone: str, heading: str = "📋 Your booking") -> None:
    bookings = [b for b in sheets.find_bookings(phone) if schedule.is_upcoming(b)]
    if not bookings:
        return _show(phone, menus.actions("You have no upcoming bookings."))
    for booking in bookings:
        _show(phone, menus.booking_card(booking, heading))


def cancel(phone: str, booking_id: str | None) -> None:
    if not booking_id:
        return show_my_bookings(phone, heading="Tap Cancel on the booking you want to cancel:")
    booking = sheets.cancel_booking_row(booking_id, phone)
    if booking is None:
        return _show(phone, menus.actions("I couldn't find that booking."))
    when = f"{menus.fmt_date(booking['date'])} at {menus.fmt_time(booking['time'])}"
    _show(
        phone,
        menus.actions(f"Booking {booking['booking_id']} ({booking['service']}, {when}) is cancelled. The slot is free again."),
    )


# ---------------------------------------------------------------- human handoff

def go_to_staff(phone: str, name: str, reason: str) -> None:
    last_typed = next(
        (m["text"] for m in reversed(history.get_history(phone)) if m["role"] == "user" and not m["text"].startswith("[")),
        "",
    )
    handoff.set_handoff(phone, True)
    handoff.notify_staff(phone, name, reason, last_typed)
    _say(phone, "Connecting you to our team 💬 They'll reply shortly.")
