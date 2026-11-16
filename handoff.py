"""Human handoff: the per-customer 'bot is silent' flag, and messages to the staff number."""
import logging

import config
import db
import whatsapp

log = logging.getLogger(__name__)

with db.connect() as _con:
    _con.execute("CREATE TABLE IF NOT EXISTS handoff (phone TEXT PRIMARY KEY, active INTEGER NOT NULL)")


def set_handoff(phone: str, active: bool) -> None:
    # INSERT OR REPLACE gives the row a new rowid, so "most recent handoff" = highest rowid.
    with db.connect() as con:
        con.execute("INSERT OR REPLACE INTO handoff (phone, active) VALUES (?, ?)", (phone, int(active)))


def is_handoff(phone: str) -> bool:
    with db.connect() as con:
        row = con.execute("SELECT active FROM handoff WHERE phone = ?", (phone,)).fetchone()
    return bool(row and row["active"])


def resume(phone: str | None = None) -> str | None:
    """Turn the bot back on for one customer (or the most recent handoff). Returns the phone, or None."""
    with db.connect() as con:
        if phone is None:
            row = con.execute("SELECT phone FROM handoff WHERE active = 1 ORDER BY rowid DESC LIMIT 1").fetchone()
            phone = row["phone"] if row else None
        elif not con.execute("SELECT 1 FROM handoff WHERE phone = ? AND active = 1", (phone,)).fetchone():
            phone = None
        if phone is None:
            return None
        con.execute("UPDATE handoff SET active = 0 WHERE phone = ?", (phone,))
    return phone


def notify_staff(phone: str, name: str, reason: str, last_message: str) -> None:
    if not config.STAFF_NUMBER:
        log.warning("STAFF_NUMBER is not set; handoff for %s was not forwarded", phone)
        return
    whatsapp.send_text(
        config.STAFF_NUMBER,
        f"🔔 Handoff request\n"
        f"Customer: {name or 'Unknown'} (+{phone})\n"
        f"Reason: {reason}\n"
        f"Last message: {last_message or '-'}\n\n"
        f"Reply to them directly. Send \"resume {phone}\" here to turn the bot back on for them.",
    )


def relay_to_staff(phone: str, name: str, text: str) -> None:
    """While a customer is in handoff, forward what they write to the staff number."""
    if not config.STAFF_NUMBER or phone == config.STAFF_NUMBER:
        return
    whatsapp.send_text(config.STAFF_NUMBER, f"💬 {name or 'Customer'} (+{phone}): {text}")
