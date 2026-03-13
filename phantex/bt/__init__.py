"""BT (Bluetooth) blueprint."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("bt", __name__, url_prefix="/bt")

from phantex.bt import views as _views  # noqa: E402, F401
