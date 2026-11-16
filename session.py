"""Half-finished booking per customer: which service / date / time they have picked so far."""
import json

import db

with db.connect() as _con:
    _con.execute("CREATE TABLE IF NOT EXISTS sessions (phone TEXT PRIMARY KEY, data TEXT NOT NULL)")


def get_session(phone: str) -> dict:
    with db.connect() as con:
        row = con.execute("SELECT data FROM sessions WHERE phone = ?", (phone,)).fetchone()
    return json.loads(row["data"]) if row else {}


def set_session(phone: str, **fields) -> None:
    """Merge fields into the session. A value of None removes that field."""
    data = get_session(phone)
    for key, value in fields.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    with db.connect() as con:
        con.execute("INSERT OR REPLACE INTO sessions (phone, data) VALUES (?, ?)", (phone, json.dumps(data)))


def clear_session(phone: str) -> None:
    with db.connect() as con:
        con.execute("DELETE FROM sessions WHERE phone = ?", (phone,))
