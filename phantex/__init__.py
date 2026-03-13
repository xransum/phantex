"""Phantex -- local OSINT recon terminal."""

from __future__ import annotations

__version__ = "0.1.0"


def run() -> None:
    """Entry point for the phantex CLI."""
    from phantex.app import create_app

    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)
