"""BTE (Bluetooth Terminal Explorer) blueprint."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("bte", __name__, url_prefix="/bte")

from phantex.bte import views as _views  # noqa: E402, F401
