"""WTE background scan task.

The APScheduler job is defined here. It calls scan_wifi() from engine.py
and merges results into the shared store.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from phantex.wte.engine import (
    _merge_records,
    _store_lock,
    scan_wifi,
)

logger = logging.getLogger(__name__)


def run_scan(app: object = None) -> None:
    """Execute one full WiFi scan cycle and update the store.

    Called by APScheduler on a fixed interval. Runs in a background thread.
    If *app* is provided (a Flask app instance), an app context is pushed so
    that history.upsert_network can use the SQLite connection. When *app* is
    None (e.g. tests that bypass the scheduler) the upsert is skipped.
    """
    import phantex.wte.engine as _engine

    logger.debug("WTE scan cycle starting")

    records, warning = scan_wifi()

    upsert_fn = None
    ctx = None
    if app is not None:
        try:
            from phantex.wte.history import upsert_network

            ctx = app.app_context()  # type: ignore[union-attr]
            ctx.push()
            upsert_fn = upsert_network
        except Exception:  # noqa: BLE001
            pass

    try:
        _merge_records(records, upsert_fn=upsert_fn)
    finally:
        if ctx is not None:
            ctx.pop()

    with _store_lock:
        _engine._last_scan = datetime.now(tz=UTC)
        _engine._scan_warning = warning

    logger.debug(
        "WTE scan cycle complete: %d networks, warning=%s",
        len(records),
        warning,
    )
