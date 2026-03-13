"""BT background scan task.

The APScheduler job is defined here. It calls both scan functions from
engine.py and merges results into the shared store.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from phantex.bt.engine import (
    _merge_records,
    _store_lock,
    scan_ble,
    scan_classic,
)

logger = logging.getLogger(__name__)


def run_scan(ble_duration: float = 3.0) -> None:
    """Execute one full scan cycle (BLE + classic) and update the store.

    Called by APScheduler on a fixed interval. Runs in a background thread.
    Pushes a Flask app context so that history.upsert_device can use
    current_app / the SQLite connection.
    """
    import phantex.bt.engine as _engine

    logger.debug("BT scan cycle starting")

    ble_records, ble_warning = scan_ble(duration=ble_duration)
    classic_records, classic_warning = scan_classic()

    all_records = ble_records + classic_records

    # Attempt to write history inside an app context.  If no app has been
    # created yet (e.g. during tests that bypass the scheduler) the import
    # or context push will fail gracefully and we fall back to no upsert.
    upsert_fn = None
    ctx = None
    try:
        from flask import current_app

        from phantex.bt.history import upsert_device

        app = current_app._get_current_object()  # type: ignore[attr-defined]
        ctx = app.app_context()
        ctx.push()
        upsert_fn = upsert_device
    except Exception:  # noqa: BLE001
        pass

    try:
        _merge_records(all_records, upsert_fn=upsert_fn)
    finally:
        if ctx is not None:
            ctx.pop()

    warning_parts = [w for w in (ble_warning, classic_warning) if w]
    combined_warning = "; ".join(warning_parts) if warning_parts else None

    with _store_lock:
        _engine._last_scan = datetime.now(tz=UTC)
        _engine._scan_warning = combined_warning

    logger.debug(
        "BT scan cycle complete: %d devices, warning=%s",
        len(all_records),
        combined_warning,
    )
