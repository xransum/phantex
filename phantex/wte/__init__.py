"""WTE (Wireless Terminal Explorer) blueprint."""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("wte", __name__, url_prefix="/wte")

from phantex.wte import views as _views  # noqa: E402, F401
