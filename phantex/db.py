"""SQLite database helpers.

A single database file lives at DB_PATH (default: var/db/phantex.db).
Connections are per-thread via threading.local() -- SQLite connections must
not be shared across threads.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from flask import Flask

_local = threading.local()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bt_history (
    mac          TEXT    NOT NULL PRIMARY KEY,
    name         TEXT    NOT NULL,
    device_type  TEXT    NOT NULL,
    rssi         INTEGER,
    device_class TEXT,
    first_seen   TEXT    NOT NULL,
    last_seen    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS wte_history (
    bssid      TEXT    NOT NULL PRIMARY KEY,
    ssid       TEXT    NOT NULL,
    channel    INTEGER,
    signal     INTEGER,
    security   TEXT,
    first_seen TEXT    NOT NULL,
    last_seen  TEXT    NOT NULL
);
"""


def init_db(app: Flask) -> None:
    """Create the database directory, file, and schema if they do not exist."""
    db_path: Path = Path(app.config["DB_PATH"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db(app: Flask) -> sqlite3.Connection:
    """Return the thread-local SQLite connection, opening it if needed."""
    db_path = str(Path(app.config["DB_PATH"]))
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(db_path)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn  # type: ignore[return-value]


def close_db() -> None:
    """Close and discard the thread-local connection."""
    conn: sqlite3.Connection | None = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
