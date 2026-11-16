"""Builds the dropdowns and button menus as plain dicts. Pure: no sending, no storage.

A menu is either
  {"kind": "list",    "body", "button", "section", "rows": [{"id","title","description"}], "header"}
  {"kind": "buttons", "body", "buttons": [{"id","title"}]}
and whatsapp.send_menu() knows how to send both.

Option ids are the contract with router.py:
  menu_book | menu_check | menu_services | menu_info | menu_staff | menu_main
  svc_<service id> | date_<YYYY-MM-DD> | slot_<YYYY-MM-DD>_<HH:MM>
  confirm_yes | confirm_change | cancel_<booking id>
"""
from datetime import datetime, timedelta

import config


# ---------------------------------------------------------------- formatting

def fmt_time(time: str) -> str:
    """'18:00' -> '6:00 PM'"""
    return datetime.strptime(time, "%H:%M").strftime("%I:%M %p").lstrip("0")


def fmt_date(date: str) -> str:
    """'2026-11-15' -> 'Sun, 15 Nov'"""
    d = datetime.strptime(date, "%Y-%m-%d")
    return f"{d.strftime('%a')}, {d.day} {d.strftime('%b')}"


def _with_intro(intro: str | None, default: str) -> str:
    return f"{intro}\n\n{default}" if intro else default


def _row(option_id: str, title: str, description: str = "") -> dict:
    return {"id": option_id, "title": title, "description": description}


def _list(body: str, button: str, section: str, rows: list[dict], header: str | None = None) -> dict:
    return {"kind": "list", "body": body, "button": button, "section": section, "rows": rows, "header": header}


def _buttons(body: str, *buttons: tuple[str, str]) -> dict:
    return {"kind": "buttons", "body": body, "buttons": [{"id": i, "title": t} for i, t in buttons]}


# ---------------------------------------------------------------- dropdowns

def main_menu(intro: str | None = None) -> dict:
    body = intro or f"Hi! 👋 Welcome to {config.SALON_NAME}.\nHow can we help you today?"
    return _list(
        body,
        "View options",
        "Menu",
        [
            _row("menu_book", "Book appointment", "Pick a service and a time"),
            _row("menu_check", "Check my booking", "See or cancel your bookings"),
            _row("menu_services", "Services & prices", "What we offer"),
            _row("menu_info", "Salon info", "Address and opening hours"),
            _row("menu_staff", "Talk to staff", "Chat with our team"),
        ],
        header=f"✨ {config.SALON_NAME}",
    )


def services_menu(services: list[dict], intro: str | None = None) -> dict:
    rows = [_row(f"svc_{s['id']}", s["name"], f"₹{s['price']} · 1 hour") for s in services]
    return _list(_with_intro(intro, "What would you like to book?"), "Choose service", "Services", rows)


def dates_menu(dates: list[str], today: str, intro: str | None = None) -> dict:
    tomorrow = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)).date().isoformat()
    labels = {today: "Today", tomorrow: "Tomorrow"}
    rows = [_row(f"date_{d}", fmt_date(d), labels.get(d, "")) for d in dates]
    return _list(_with_intro(intro, "Which day works for you?"), "Pick a day", "Dates", rows)


def slots_menu(date: str, times: list[str], intro: str | None = None) -> dict:
    rows = [_row(f"slot_{date}_{t}", fmt_time(t)) for t in times]
    return _list(
        _with_intro(intro, f"Open times on {fmt_date(date)}:"), "View times", "Time slots", rows
    )


# ---------------------------------------------------------------- buttons

def confirm_buttons(service: dict, date: str, time: str) -> dict:
    body = (
        "Please confirm your booking:\n\n"
        f"✂️ {service['name']} (₹{service['price']})\n"
        f"📅 {fmt_date(date)}\n"
        f"🕐 {fmt_time(time)}"
    )
    return _buttons(body, ("confirm_yes", "Confirm"), ("confirm_change", "Change"))


def booking_card(booking: dict, heading: str) -> dict:
    body = (
        f"{heading}\n\n"
        f"🆔 {booking['booking_id']}\n"
        f"✂️ {booking['service']} (₹{booking['price']})\n"
        f"📅 {fmt_date(booking['date'])} · 🕐 {fmt_time(booking['time'])}"
    )
    return _buttons(body, (f"cancel_{booking['booking_id']}", "Cancel booking"), ("menu_main", "Main menu"))


def actions(body: str) -> dict:
    """A message with 'Book now' and 'Main menu' buttons under it."""
    return _buttons(body, ("menu_book", "Book now"), ("menu_main", "Main menu"))


def services_info(services: list[dict]) -> dict:
    lines = "\n".join(f"• {s['name']} — ₹{s['price']}" for s in services)
    return actions(f"💇 Our services (1 hour each)\n\n{lines}")


def salon_info() -> dict:
    opens, closes = fmt_time(f"{config.OPEN_HOUR:02d}:00"), fmt_time(f"{config.CLOSE_HOUR:02d}:00")
    return actions(f"📍 {config.SALON_NAME}\n{config.SALON_ADDRESS}\n\n🕙 Open every day, {opens} – {closes}")
