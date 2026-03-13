"""WTE session history -- SQLite-backed network history.

Separate from the live network store in engine.py. Networks are never
evicted here; every BSSID seen since the DB was last cleared is retained.
first_seen is preserved on revisit.
"""

from __future__ import annotations

from flask import current_app

from phantex.db import get_db
from phantex.wte.engine import NetworkRecord


def upsert_network(record: NetworkRecord) -> None:
    """Insert a new network or update ssid/signal/security/last_seen.

    first_seen is written only on the initial INSERT and never overwritten.
    """
    db = get_db(current_app._get_current_object())  # type: ignore[attr-defined]
    db.execute(
        """
        INSERT INTO wte_history (bssid, ssid, channel, signal, security, first_seen, last_seen)
        VALUES (:bssid, :ssid, :channel, :signal, :security, :first_seen, :last_seen)
        ON CONFLICT(bssid) DO UPDATE SET
            ssid       = excluded.ssid,
            channel    = excluded.channel,
            signal     = excluded.signal,
            security   = excluded.security,
            last_seen  = excluded.last_seen
        """,
        {
            "bssid": record.bssid,
            "ssid": record.ssid,
            "channel": record.channel,
            "signal": record.signal,
            "security": record.security,
            "first_seen": record.first_seen.isoformat(),
            "last_seen": record.last_seen.isoformat(),
        },
    )
    db.commit()


def get_history() -> list[dict[str, object]]:
    """Return all history rows ordered by first_seen descending."""
    db = get_db(current_app._get_current_object())  # type: ignore[attr-defined]
    rows = db.execute(
        "SELECT bssid, ssid, channel, signal, security, first_seen, last_seen "
        "FROM wte_history ORDER BY first_seen DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def get_history_count() -> int:
    """Return the total number of unique networks in history."""
    db = get_db(current_app._get_current_object())  # type: ignore[attr-defined]
    row = db.execute("SELECT COUNT(*) FROM wte_history").fetchone()
    return int(row[0])


def clear_history() -> None:
    """Delete all rows from wte_history."""
    db = get_db(current_app._get_current_object())  # type: ignore[attr-defined]
    db.execute("DELETE FROM wte_history")
    db.commit()
