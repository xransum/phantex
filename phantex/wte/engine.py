"""WTE scanner engine.

Pure scanning logic -- no Flask, no APScheduler dependencies.
scan_wifi() wraps nmcli and returns results independently so it can be
tested and called from any context.
"""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class NetworkRecord:
    """A single detected WiFi network."""

    bssid: str
    ssid: str
    channel: int | None
    signal: int | None  # nmcli signal strength 0-100
    security: str | None
    first_seen: datetime
    last_seen: datetime

    def to_dict(self) -> dict[str, str | int | None]:
        """Serialise to a JSON-safe dict."""
        return {
            "bssid": self.bssid,
            "ssid": self.ssid,
            "channel": self.channel,
            "signal": self.signal,
            "security": self.security,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


def _unescape_nmcli(value: str) -> str:
    """Unescape nmcli terse-mode backslash sequences.

    nmcli -t escapes colons inside values as \\: and backslashes as \\\\.
    """
    return value.replace("\\:", ":").replace("\\\\", "\\")


def scan_wifi() -> tuple[list[NetworkRecord], str | None]:
    """Scan for nearby WiFi networks via nmcli.

    Returns (records, warning) where warning is None on success.
    Never raises -- errors are surfaced as the warning string.

    Requires nmcli (NetworkManager CLI) to be installed. On systems without
    nmcli a graceful warning is returned and an empty list.
    """
    try:
        result = subprocess.run(
            [
                "nmcli",
                "--terse",
                "--fields",
                "SSID,BSSID,CHAN,SIGNAL,SECURITY",
                "device",
                "wifi",
                "list",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return [], f"WiFi scan failed: {stderr or 'unknown error'}"

        records: list[NetworkRecord] = []
        seen_bssids: set[str] = set()
        now = datetime.now(tz=UTC)

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            # nmcli -t separates fields with unescaped colons.
            # We split on unescaped colons only (escaped ones are \:).
            # Strategy: replace \: with a placeholder, split on :, restore.
            placeholder = "\x00"
            parts = line.replace("\\:", placeholder).split(":")
            parts = [p.replace(placeholder, ":") for p in parts]

            if len(parts) < 5:  # noqa: PLR2004
                continue

            ssid_raw, bssid_raw, chan_raw, signal_raw, security_raw = (
                parts[0],
                parts[1],
                parts[2],
                parts[3],
                ":".join(parts[4:]),
            )

            ssid = _unescape_nmcli(ssid_raw) or "[hidden]"
            bssid = _unescape_nmcli(bssid_raw)

            if not bssid or bssid in seen_bssids:
                continue
            seen_bssids.add(bssid)

            try:
                channel: int | None = int(chan_raw) if chan_raw.strip() else None
            except ValueError:
                channel = None

            try:
                signal: int | None = int(signal_raw) if signal_raw.strip() else None
            except ValueError:
                signal = None

            security_str = _unescape_nmcli(security_raw).strip() or None

            records.append(
                NetworkRecord(
                    bssid=bssid,
                    ssid=ssid,
                    channel=channel,
                    signal=signal,
                    security=security_str,
                    first_seen=now,
                    last_seen=now,
                )
            )

        return records, None

    except FileNotFoundError:
        return [], "WiFi scan unavailable: nmcli not found"
    except subprocess.TimeoutExpired:
        return [], "WiFi scan timed out"
    except PermissionError:
        return [], "WiFi scan unavailable: insufficient permissions"
    except Exception as exc:  # noqa: BLE001
        return [], f"WiFi scan failed: {exc}"


# ---------------------------------------------------------------------------
# Thread-safe network store -- shared across all scan cycles
# ---------------------------------------------------------------------------

_store_lock = threading.Lock()
_network_store: dict[str, NetworkRecord] = {}
_last_scan: datetime | None = None
_scan_warning: str | None = None


def get_store_snapshot() -> tuple[list[NetworkRecord], datetime | None, str | None]:
    """Return a consistent snapshot of the network store."""
    with _store_lock:
        return list(_network_store.values()), _last_scan, _scan_warning


def _merge_records(new_records: list[NetworkRecord], upsert_fn: object = None) -> None:
    """Merge new scan results into the store, preserving first_seen.

    If *upsert_fn* is provided it is called for each record after the
    in-memory store is updated.
    """
    with _store_lock:
        for record in new_records:
            existing = _network_store.get(record.bssid)
            if existing is not None:
                record.first_seen = existing.first_seen
            _network_store[record.bssid] = record
            if upsert_fn is not None:
                try:  # noqa: SIM105
                    upsert_fn(record)  # type: ignore[operator]
                except Exception:  # noqa: BLE001
                    pass
