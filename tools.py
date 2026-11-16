"""The actions the LLM can trigger. The model only picks a tool and arguments;
this file checks every argument against reality, then calls the matching step in flows.py."""
import logging
from datetime import datetime

import flows
import schedule
import session
import sheets

log = logging.getLogger(__name__)


def build_context(phone: str) -> dict:
    """What the LLM needs to know to choose well."""
    return {
        "now": schedule.now(),
        "services": sheets.get_services(),
        "draft": session.get_session(phone),
        "dates": schedule.bookable_dates(),
    }


# ---------------------------------------------------------------- argument checks (None = not usable)

def _service(value, services: list[dict]) -> str | None:
    wanted = str(value or "").strip().lower()
    for s in services:
        if wanted in (s["id"].lower(), s["name"].lower()):
            return s["id"]
    return None


def _date(value) -> str | None:
    value = str(value or "").strip()
    return value if value in schedule.bookable_dates() else None


def _time(value) -> str | None:
    value = str(value or "").strip()
    for pattern in ("%H:%M", "%H"):
        try:
            normalized = datetime.strptime(value, pattern).strftime("%H:%M")
        except ValueError:
            continue
        return normalized if normalized in schedule.slot_times() else None
    return None


# ---------------------------------------------------------------- the five tools

def _create_booking(msg, args: dict) -> None:
    services = sheets.get_services()
    flows.start_booking(
        msg.phone,
        service=_service(args.get("service"), services),
        date=_date(args.get("date")),
        time=_time(args.get("time")),
    )


def _get_slots(msg, args: dict) -> None:
    services = sheets.get_services()
    flows.show_slots(msg.phone, date=_date(args.get("date")), service=_service(args.get("service"), services))


def _check_booking(msg, args: dict) -> None:
    flows.show_my_bookings(msg.phone)


def _cancel_booking(msg, args: dict) -> None:
    booking_id = str(args.get("booking_id") or "").strip().upper()
    flows.cancel(msg.phone, booking_id or None)


def _handoff_to_staff(msg, args: dict) -> None:
    flows.go_to_staff(msg.phone, msg.name, str(args.get("reason") or "Customer asked for a person"))


_TOOLS = {
    "create_booking": _create_booking,
    "get_slots": _get_slots,
    "check_booking": _check_booking,
    "cancel_booking": _cancel_booking,
    "handoff_to_staff": _handoff_to_staff,
}


def run_tool(msg, name: str, args: dict) -> bool:
    """Run the tool the LLM chose. Returns False if the name is not one of ours."""
    tool = _TOOLS.get(name)
    if tool is None:
        log.warning("LLM chose unknown tool %r", name)
        return False
    tool(msg, args or {})
    return True
