"""Chat memory: the last few messages per customer, used as context for the LLM."""
import db

with db.connect() as _con:
    _con.execute(
        """CREATE TABLE IF NOT EXISTS messages (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               phone TEXT NOT NULL,
               role TEXT NOT NULL,        -- 'user' or 'bot'
               text TEXT NOT NULL
           )"""
    )


def save_message(phone: str, role: str, text: str) -> None:
    with db.connect() as con:
        con.execute("INSERT INTO messages (phone, role, text) VALUES (?, ?, ?)", (phone, role, text))


def get_history(phone: str, limit: int = 6) -> list[dict]:
    """Most recent `limit` messages, oldest first: [{'role': 'user'|'bot', 'text': str}, ...]."""
    with db.connect() as con:
        rows = con.execute(
            "SELECT role, text FROM messages WHERE phone = ? ORDER BY id DESC LIMIT ?", (phone, limit)
        ).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in reversed(rows)]
