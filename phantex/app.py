"""Flask application factory."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

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
    _init_database(app)
    _register_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_context_processors(app)

    return app


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _configure_logging(app: Flask) -> None:
    """Set up rotating file logging + quiet terminal handler.

    - File handler: DEBUG+ -> var/log/phantex.log, 5 MB x 3 backups.
    - Terminal handler: WARNING+ only via a filter, with one exception --
      werkzeug.serving INFO records are allowed through so the startup
      banner ("* Running on http://...") still appears.
    - APScheduler is silenced on the terminal (file still captures it).
    - In TESTING mode logging is left at its default to avoid cluttering test output.
    """
    if app.testing:
        return

    log_dir: Path = Path(app.config["LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "phantex.log"

    file_level = logging.DEBUG if app.debug else logging.INFO
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler -- captures everything
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=app.config["LOG_MAX_BYTES"],
        backupCount=app.config["LOG_BACKUP_COUNT"],
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(fmt)

    # Terminal handler -- WARNING+ for everything, except the werkzeug startup
    # banner ("* Running on http://...") which comes through at INFO.
    # Startup banner records are emitted as-is (no reformatting) so Werkzeug's
    # own colour codes and leading " * " prefix are preserved.
    _plain_fmt = logging.Formatter("%(message)s")

    class _StartupBannerFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if record.name == "werkzeug" and record.levelno == logging.INFO:
                msg = record.getMessage()
                return "Running on" in msg or "Press CTRL+C" in msg
            return record.levelno >= logging.WARNING

    class _SelectiveFormatter(logging.Formatter):
        """Use plain formatting for werkzeug startup lines, full fmt for everything else."""

        def format(self, record: logging.LogRecord) -> str:
            if record.name == "werkzeug" and record.levelno == logging.INFO:
                return _plain_fmt.format(record)
            return fmt.format(record)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)  # gate via filter, not level
    stream_handler.setFormatter(_SelectiveFormatter())
    stream_handler.addFilter(_StartupBannerFilter())

    # Configure the root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # Remove any handlers basicConfig or Flask may have already installed
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    # werkzeug at INFO so the startup banner records pass the logger level check.
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    app.logger.info("Logging initialised -- file: %s", log_file)


def _init_database(app: Flask) -> None:
    """Initialise the SQLite database and create tables if absent."""
    from phantex.db import init_db

    init_db(app)


def _register_extensions(app: Flask) -> None:
    from phantex.bt.tasks import run_scan
    from phantex.extensions import scheduler

    if not app.testing:
        interval = app.config.get("BT_SCAN_INTERVAL", 5)
        ble_duration = app.config.get("BT_BLE_SCAN_DURATION", 3.0)
        scheduler.add_job(
            run_scan,
            trigger="interval",
            seconds=interval,
            kwargs={"ble_duration": ble_duration},
            id="bt_scan",
            replace_existing=True,
        )
        if not scheduler.running:
            scheduler.start()
        app.extensions["scheduler"] = scheduler


def _register_blueprints(app: Flask) -> None:
    from phantex.bt import bp as bt_bp

    app.register_blueprint(bt_bp)

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
