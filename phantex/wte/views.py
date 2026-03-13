"""WTE blueprint views -- /wte and /wte/data."""

from __future__ import annotations

from flask import jsonify, render_template

from phantex.wte import bp
from phantex.wte.engine import get_store_snapshot


@bp.get("/")
def index() -> str:
    """Render the WTE scanner page."""
    return render_template("wte/index.html")


@bp.get("/data")
def data():  # type: ignore[return]
    """Return current network store as JSON.

    Response shape:
    {
        "networks": [ NetworkRecord.to_dict(), ... ],
        "scan_warning": str | null,
        "last_scan": ISO8601 string | null
    }
    """
    networks, last_scan, warning = get_store_snapshot()
    return jsonify(
        {
            "networks": [n.to_dict() for n in networks],
            "scan_warning": warning,
            "last_scan": last_scan.isoformat() if last_scan else None,
        }
    )


@bp.get("/history")
def history():  # type: ignore[return]
    """Return the full session history from SQLite.

    Response shape:
    {
        "networks": [ row dict, ... ],
        "total": int
    }
    """
    from phantex.wte.history import get_history, get_history_count

    networks = get_history()
    total = get_history_count()
    return jsonify({"networks": networks, "total": total})


@bp.post("/history/clear")
def history_clear():  # type: ignore[return]
    """Clear the full session history.

    Response shape:
    {
        "ok": true
    }
    """
    from phantex.wte.history import clear_history

    clear_history()
    return jsonify({"ok": True})
