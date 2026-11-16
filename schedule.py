"""Business rules for time: open hours, 1-hour slots, which dates are bookable, which slots are free.
Same hours every day. IST everywhere."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
import sheets

_TZ = ZoneInfo(config.TIMEZONE)


def now() -> datetime:
    return datetime.now(_TZ)


def today_str() -> str:
    return now().date().isoformat()


def slot_times() -> list[str]:
    """Every slot start of a day: ['10:00', '11:00', ... '18:00']."""
    return [f"{hour:02d}:00" for hour in range(config.OPEN_HOUR, config.CLOSE_HOUR)]


def _slot_start(date: str, time: str) -> datetime:
    return datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=_TZ)


def bookable_dates() -> list[str]:
    """The next DAYS_AHEAD days, starting today (or tomorrow if today's last slot has passed)."""
    start = now().date()
    days = [(start + timedelta(days=i)).isoformat() for i in range(config.DAYS_AHEAD)]
    if _slot_start(days[0], slot_times()[-1]) <= now():
        days = days[1:]
    return days


def open_slots(date: str) -> list[str]:
    """Slot times on a date that are in the future and not already booked."""
    booked = sheets.get_booked_times(date)
    current = now()
    return [t for t in slot_times() if t not in booked and _slot_start(date, t) > current]


def is_upcoming(booking: dict) -> bool:
    return _slot_start(booking["date"], booking["time"]) > now()
