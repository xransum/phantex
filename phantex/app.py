"""Flask application factory."""

from __future__ import annotations

import logging

from flask import Flask, render_template

from phantex import __version__


def create_app(config: str = "phantex.settings.DevelopmentConfig") -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Dotted path to a config class. Overridable for testing.

    Returns:
        A fully configured Flask app instance.
    """
    app = Flask(__name__)
    app.config.from_object(config)
    # Allow individual overrides via PHANTEX_-prefixed env vars.
    app.config.from_prefixed_env(prefix="PHANTEX")

    _configure_logging(app)
    _register_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_context_processors(app)

    return app


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _register_extensions(app: Flask) -> None:
    from phantex.bte.tasks import run_scan
    from phantex.extensions import scheduler

    if not app.testing:
        interval = app.config.get("BTE_SCAN_INTERVAL", 5)
        ble_duration = app.config.get("BTE_BLE_SCAN_DURATION", 3.0)
        scheduler.add_job(
            run_scan,
            trigger="interval",
            seconds=interval,
            kwargs={"ble_duration": ble_duration},
            id="bte_scan",
            replace_existing=True,
        )
        if not scheduler.running:
            scheduler.start()
        app.extensions["scheduler"] = scheduler


def _register_blueprints(app: Flask) -> None:
    from phantex.bte import bp as bte_bp

    app.register_blueprint(bte_bp)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(e: Exception) -> tuple[str, int]:
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e: Exception) -> tuple[str, int]:
        return render_template("errors/500.html"), 500


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_globals() -> dict[str, str]:
        return {"app_version": __version__}
