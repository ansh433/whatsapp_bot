"""Opens SQLite connections. The only file that knows where local data is stored."""
import sqlite3
from contextlib import contextmanager

import config


@contextmanager
def connect():
    """Yield a fresh connection (one per call, so it is safe across threads); commit and close after."""
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()
