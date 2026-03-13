"""Configuration classes for Phantex.

Usage in create_app():
    app.config.from_object("phantex.settings.DevelopmentConfig")

Override individual values via environment variables prefixed with PHANTEX_:
    PHANTEX_SECRET_KEY=mysecret uv run flask run
"""

from __future__ import annotations

import os


class BaseConfig:
    """Shared base configuration."""

    SECRET_KEY: str = os.environ.get("PHANTEX_SECRET_KEY", "dev-secret-change-me")
    DEBUG: bool = False
    TESTING: bool = False

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
