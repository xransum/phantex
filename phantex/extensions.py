"""Application-level extension instances (unbound).

Extensions are instantiated here as module-level singletons and bound to
the Flask app inside create_app() via init_app(). This avoids circular
imports and keeps the factory clean.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

scheduler: BackgroundScheduler = BackgroundScheduler()
