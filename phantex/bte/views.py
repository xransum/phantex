"""BTE blueprint views -- /bte and /bte/data."""

from __future__ import annotations

from flask import jsonify, render_template

from phantex.bte import bp
from phantex.bte.engine import get_store_snapshot


@bp.get("/")
def index() -> str:
    """Render the BTE scanner page."""
    return render_template("bte/index.html")


@bp.get("/data")
def data():  # type: ignore[return]
    """Return current device store as JSON.

    Response shape:
    {
        "devices": [ DeviceRecord.to_dict(), ... ],
        "scan_warning": str | null,
        "last_scan": ISO8601 string | null
    }
    """
    devices, last_scan, warning = get_store_snapshot()
    return jsonify(
        {
            "devices": [d.to_dict() for d in devices],
            "scan_warning": warning,
            "last_scan": last_scan.isoformat() if last_scan else None,
        }
    )
