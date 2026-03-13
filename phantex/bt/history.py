"""BT session history -- SQLite-backed device history.

Separate from the live device store in engine.py. Devices are never
evicted here; every MAC seen since the DB was last cleared is retained.
first_seen is preserved on revisit (INSERT OR IGNORE strategy).
"""

from __future__ import annotations

from flask import current_app

from phantex.bt.engine import DeviceRecord
from phantex.db import get_db


def upsert_device(record: DeviceRecord) -> None:
    """Insert a new device or update name/rssi/device_class/last_seen.

    first_seen is written only on the initial INSERT and never overwritten.
    """
    db = get_db(current_app._get_current_object())  # type: ignore[attr-defined]
    db.execute(
        """
        INSERT INTO bt_history (mac, name, device_type, rssi, device_class, first_seen, last_seen)
        VALUES (:mac, :name, :device_type, :rssi, :device_class, :first_seen, :last_seen)
        ON CONFLICT(mac) DO UPDATE SET
            name         = excluded.name,
            rssi         = excluded.rssi,
            device_class = excluded.device_class,
            last_seen    = excluded.last_seen
        """,
        {
            "mac": record.mac,
            "name": record.name,
            "device_type": record.device_type,
            "rssi": record.rssi,
            "device_class": record.device_class,
            "first_seen": record.first_seen.isoformat(),
            "last_seen": record.last_seen.isoformat(),
        },
    )
    db.commit()


def get_history() -> list[dict[str, object]]:
    """Return all history rows ordered by first_seen descending."""
    db = get_db(current_app._get_current_object())  # type: ignore[attr-defined]
    rows = db.execute(
        "SELECT mac, name, device_type, rssi, device_class, first_seen, last_seen "
        "FROM bt_history ORDER BY first_seen DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def get_history_count() -> int:
    """Return the total number of unique devices in history."""
    db = get_db(current_app._get_current_object())  # type: ignore[attr-defined]
    row = db.execute("SELECT COUNT(*) FROM bt_history").fetchone()
    return int(row[0])


def clear_history() -> None:
    """Delete all rows from bt_history."""
    db = get_db(current_app._get_current_object())  # type: ignore[attr-defined]
    db.execute("DELETE FROM bt_history")
    db.commit()
