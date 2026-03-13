"""BT scanner engine.

Pure scanning logic -- no Flask, no APScheduler dependencies.
Both scan functions return results independently so they can be
tested and called from any context.
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class DeviceRecord:
    """A single detected Bluetooth device."""

    mac: str
    name: str
    device_type: str  # "BLE" | "Classic"
    rssi: int | None
    device_class: str | None
    first_seen: datetime
    last_seen: datetime

    def to_dict(self) -> dict[str, str | int | None]:
        """Serialise to a JSON-safe dict."""
        return {
            "mac": self.mac,
            "name": self.name,
            "device_type": self.device_type,
            "rssi": self.rssi,
            "device_class": self.device_class,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


def scan_ble(duration: float = 3.0) -> tuple[list[DeviceRecord], str | None]:
    """Run a BLE discovery scan for *duration* seconds.

    Returns (records, warning) where warning is None on success.
    Never raises -- errors are surfaced as the warning string.
    """
    try:
        from bleak import BleakScanner

        async def _discover() -> list[DeviceRecord]:
            now = datetime.now(tz=UTC)
            # return_adv=True gives us (BLEDevice, AdvertisementData) pairs
            # so we can read RSSI from the advertisement.
            discovered = await BleakScanner.discover(timeout=duration, return_adv=True)
            records: list[DeviceRecord] = []
            for device, adv in discovered.values():
                records.append(
                    DeviceRecord(
                        mac=device.address,
                        name=device.name or adv.local_name or "Unknown",
                        device_type="BLE",
                        rssi=adv.rssi,
                        device_class=None,
                        first_seen=now,
                        last_seen=now,
                    )
                )
            return records

        records = asyncio.run(_discover())
        return records, None
    except Exception as exc:  # noqa: BLE001
        return [], f"BLE scan failed: {exc}"


def scan_classic() -> tuple[list[DeviceRecord], str | None]:
    """Run a classic Bluetooth inquiry via hcitool scan.

    This call blocks for ~10 seconds (the standard inquiry window).
    Returns (records, warning) where warning is None on success.
    Never raises.
    """
    try:
        result = subprocess.run(
            ["hcitool", "scan", "--flush"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Operation not permitted" in stderr or "Cannot open HCI device" in stderr:
                return [], "Classic BT unavailable: insufficient permissions (CAP_NET_RAW required)"
            return [], f"Classic BT scan failed: {stderr or 'unknown error'}"

        records: list[DeviceRecord] = []
        now = datetime.now(tz=UTC)
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("Scanning"):
                continue
            parts = line.split(None, 1)
            if len(parts) < 1:
                continue
            mac = parts[0]
            name = parts[1] if len(parts) > 1 else "Unknown"
            records.append(
                DeviceRecord(
                    mac=mac,
                    name=name,
                    device_type="Classic",
                    rssi=None,
                    device_class=None,
                    first_seen=now,
                    last_seen=now,
                )
            )
        return records, None
    except FileNotFoundError:
        return [], "Classic BT unavailable: hcitool not found"
    except subprocess.TimeoutExpired:
        return [], "Classic BT scan timed out"
    except PermissionError:
        return [], "Classic BT unavailable: insufficient permissions (CAP_NET_RAW required)"
    except Exception as exc:  # noqa: BLE001
        return [], f"Classic BT scan failed: {exc}"


# ---------------------------------------------------------------------------
# Thread-safe device store -- shared across all scan cycles
# ---------------------------------------------------------------------------

_store_lock = threading.Lock()
_device_store: dict[str, DeviceRecord] = {}
_last_scan: datetime | None = None
_scan_warning: str | None = None


def get_store_snapshot() -> tuple[list[DeviceRecord], datetime | None, str | None]:
    """Return a consistent snapshot of the device store."""
    with _store_lock:
        return list(_device_store.values()), _last_scan, _scan_warning


def _merge_records(new_records: list[DeviceRecord]) -> None:
    """Merge new scan results into the store, preserving first_seen."""
    with _store_lock:
        for record in new_records:
            existing = _device_store.get(record.mac)
            if existing is not None:
                record.first_seen = existing.first_seen
            _device_store[record.mac] = record
