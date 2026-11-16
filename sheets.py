"""Google Sheets read/write. The only file that knows the sheet layout.

Two tabs:
  Services  - id, name, price
  Bookings  - booking_id, phone, name, service, price, date, time, status, created_at
Open slots are not stored: they are derived from the Bookings tab (see schedule.py).
"""
import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import config

log = logging.getLogger(__name__)

SERVICE_HEADERS = ["id", "name", "price"]
BOOKING_HEADERS = ["booking_id", "phone", "name", "service", "price", "date", "time", "status", "created_at"]
CONFIRMED = "Confirmed"
CANCELLED = "Cancelled"
_ID_PREFIX = "GS"

_spreadsheet_cache = None
_write_lock = threading.Lock()   # makes "is the slot still free? then book it" one step


def _spreadsheet():
    global _spreadsheet_cache
    if _spreadsheet_cache is None:
        import gspread   # imported lazily so the rest of the app loads without credentials

        client = gspread.service_account(filename=config.GOOGLE_CREDENTIALS_FILE)
        _spreadsheet_cache = client.open_by_key(config.SHEET_ID)
    return _spreadsheet_cache


def _records(tab: str) -> list[dict]:
    # numericise_ignore keeps phone numbers and times as text instead of turning them into numbers
    rows = _spreadsheet().worksheet(tab).get_all_records(numericise_ignore=["all"])
    return [{k: str(v) for k, v in row.items()} for row in rows]


def _price(value: str) -> int:
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else 0


# ---------------------------------------------------------------- services

def get_services() -> list[dict]:
    """[{'id': 'haircut', 'name': 'Haircut', 'price': 400}, ...]"""
    return [
        {"id": r["id"], "name": r["name"], "price": _price(r["price"])}
        for r in _records("Services")
        if r.get("id")
    ]


# ---------------------------------------------------------------- bookings

def _to_booking(row: dict) -> dict:
    return {**row, "price": _price(row.get("price", ""))}


def get_booked_times(date: str) -> set[str]:
    """Times already taken (confirmed bookings) on a date 'YYYY-MM-DD'."""
    return {r["time"] for r in _records("Bookings") if r["date"] == date and r["status"] == CONFIRMED}


def _next_booking_id(rows: list[dict]) -> str:
    numbers = []
    for row in rows:
        try:
            numbers.append(int(row["booking_id"].split("-")[1]))
        except (KeyError, IndexError, ValueError):
            pass
    return f"{_ID_PREFIX}-{max(numbers, default=1000) + 1}"


def add_booking(phone: str, name: str, service: dict, date: str, time: str) -> dict | None:
    """Write a confirmed booking. Returns the booking, or None if the slot was taken meanwhile."""
    with _write_lock:
        rows = _records("Bookings")
        if any(r["date"] == date and r["time"] == time and r["status"] == CONFIRMED for r in rows):
            return None
        booking = {
            "booking_id": _next_booking_id(rows),
            "phone": phone,
            "name": name or "",
            "service": service["name"],
            "price": str(service["price"]),
            "date": date,
            "time": time,
            "status": CONFIRMED,
            "created_at": datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d %H:%M"),
        }
        _spreadsheet().worksheet("Bookings").append_row(
            [booking[h] for h in BOOKING_HEADERS], value_input_option="RAW"
        )
    return _to_booking(booking)


def find_bookings(phone: str) -> list[dict]:
    """A customer's confirmed bookings, looked up by phone number."""
    return [_to_booking(r) for r in _records("Bookings") if r["phone"] == phone and r["status"] == CONFIRMED]


def cancel_booking_row(booking_id: str, phone: str) -> dict | None:
    """Mark a customer's own confirmed booking as Cancelled (frees the slot). Returns it, or None."""
    with _write_lock:
        worksheet = _spreadsheet().worksheet("Bookings")
        rows = worksheet.get_all_records(numericise_ignore=["all"])
        status_col = BOOKING_HEADERS.index("status") + 1
        for index, row in enumerate(rows, start=2):   # row 1 is the header
            row = {k: str(v) for k, v in row.items()}
            if row["booking_id"] == booking_id and row["phone"] == phone and row["status"] == CONFIRMED:
                worksheet.update_cell(index, status_col, CANCELLED)
                return _to_booking({**row, "status": CANCELLED})
    return None


# ---------------------------------------------------------------- one-time setup

def init_sheet(seed_services: list[tuple]) -> None:
    """Create the Services and Bookings tabs (with headers) and seed the services if empty."""
    import gspread

    spreadsheet = _spreadsheet()
    for title, headers in (("Services", SERVICE_HEADERS), ("Bookings", BOOKING_HEADERS)):
        try:
            worksheet = spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=title, rows=200, cols=len(headers))
        if not worksheet.row_values(1):
            worksheet.append_row(headers)
        if title == "Services" and len(worksheet.get_all_values()) < 2:
            for row in seed_services:
                worksheet.append_row(list(row), value_input_option="RAW")
