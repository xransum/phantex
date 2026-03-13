"""Configuration classes for Phantex.

Usage in create_app():
    app.config.from_object("phantex.settings.DevelopmentConfig")

Override individual values via environment variables prefixed with PHANTEX_:
    PHANTEX_SECRET_KEY=mysecret uv run flask run
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root: two levels up from this file (phantex/settings.py -> phantex/ -> repo root)
_REPO_ROOT = Path(__file__).parent.parent


class BaseConfig:
    """Shared base configuration."""

    SECRET_KEY: str = os.environ.get("PHANTEX_SECRET_KEY", "dev-secret-change-me")
    DEBUG: bool = False
    TESTING: bool = False

    # SQLite database path. Created at startup if it does not exist.
    DB_PATH: Path = Path(
        os.environ.get("PHANTEX_DB_PATH", str(_REPO_ROOT / "var" / "db" / "phantex.db"))
    )

    # Log file output directory. Created at startup if it does not exist.
    LOG_DIR: Path = Path(os.environ.get("PHANTEX_LOG_DIR", str(_REPO_ROOT / "var" / "log")))
    # Max bytes per log file before rotation.
    LOG_MAX_BYTES: int = int(os.environ.get("PHANTEX_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
    # Number of rotated backup files to keep.
    LOG_BACKUP_COUNT: int = int(os.environ.get("PHANTEX_LOG_BACKUP_COUNT", "3"))

    # Bluetooth scan interval in seconds. BLE discovery runs for
    # BT_BLE_SCAN_DURATION seconds per cycle; the interval must be larger.
    BT_SCAN_INTERVAL: int = int(os.environ.get("PHANTEX_BT_SCAN_INTERVAL", "5"))
    BT_BLE_SCAN_DURATION: float = float(os.environ.get("PHANTEX_BT_BLE_SCAN_DURATION", "3.0"))
    # Seconds after which a device is considered stale in the store.
    BT_STALE_THRESHOLD: int = int(os.environ.get("PHANTEX_BT_STALE_THRESHOLD", "30"))


class DevelopmentConfig(BaseConfig):
    """Development configuration -- debug on, verbose logging."""

    DEBUG: bool = True


class ProductionConfig(BaseConfig):
    """Production configuration."""

    DEBUG: bool = False


class TestingConfig(BaseConfig):
    """Testing configuration -- disables scheduler."""

    TESTING: bool = True
    DEBUG: bool = True
    BT_SCAN_INTERVAL: int = 999  # prevent scheduler from firing during tests
