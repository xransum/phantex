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

    Called by APScheduler on a fixed interval. Runs in a background thread
    so it must never touch Flask request context.
    """
    import phantex.bt.engine as _engine

    logger.debug("BT scan cycle starting")

    ble_records, ble_warning = scan_ble(duration=ble_duration)
    classic_records, classic_warning = scan_classic()

    all_records = ble_records + classic_records
    _merge_records(all_records)

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
