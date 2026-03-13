"""Tests for the WTE scanner engine."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from phantex.wte.engine import (
    NetworkRecord,
    _merge_records,
    _network_store,
    _store_lock,
    get_store_snapshot,
    scan_wifi,
)


@pytest.fixture(autouse=True)
def clear_store() -> None:
    """Reset the shared network store before each test."""
    with _store_lock:
        _network_store.clear()


def make_record(bssid: str = "AA:BB:CC:DD:EE:FF") -> NetworkRecord:
    now = datetime.now(tz=UTC)
    return NetworkRecord(
        bssid=bssid,
        ssid="TestNet",
        channel=6,
        signal=75,
        security="WPA2",
        first_seen=now,
        last_seen=now,
    )


class TestNetworkRecord:
    def test_to_dict_contains_expected_keys(self) -> None:
        record = make_record()
        d = record.to_dict()
        assert set(d.keys()) == {
            "bssid",
            "ssid",
            "channel",
            "signal",
            "security",
            "first_seen",
            "last_seen",
        }

    def test_to_dict_iso_timestamps(self) -> None:
        record = make_record()
        d = record.to_dict()
        datetime.fromisoformat(str(d["first_seen"]))
        datetime.fromisoformat(str(d["last_seen"]))


class TestMergeRecords:
    def test_new_record_added_to_store(self) -> None:
        record = make_record("AA:BB:CC:DD:EE:01")
        _merge_records([record])
        snapshot, _, _ = get_store_snapshot()
        assert any(n.bssid == "AA:BB:CC:DD:EE:01" for n in snapshot)

    def test_first_seen_preserved_on_update(self) -> None:
        original_time = datetime(2024, 1, 1, tzinfo=UTC)
        record = make_record("AA:BB:CC:DD:EE:02")
        record.first_seen = original_time
        _merge_records([record])

        updated = make_record("AA:BB:CC:DD:EE:02")
        _merge_records([updated])

        snapshot, _, _ = get_store_snapshot()
        stored = next(n for n in snapshot if n.bssid == "AA:BB:CC:DD:EE:02")
        assert stored.first_seen == original_time

    def test_multiple_records_merged(self) -> None:
        records = [make_record(f"AA:BB:CC:DD:EE:{i:02X}") for i in range(5)]
        _merge_records(records)
        snapshot, _, _ = get_store_snapshot()
        assert len(snapshot) == 5


class TestGetStoreSnapshot:
    def test_returns_empty_list_initially(self) -> None:
        networks, last_scan, warning = get_store_snapshot()
        assert networks == []
        assert last_scan is None
        assert warning is None

    def test_returns_copy_not_reference(self) -> None:
        _merge_records([make_record("AA:BB:CC:DD:EE:FF")])
        snapshot1, _, _ = get_store_snapshot()
        snapshot1.clear()
        snapshot2, _, _ = get_store_snapshot()
        assert len(snapshot2) == 1


class TestScanWifi:
    def test_returns_empty_list_and_warning_when_nmcli_missing(self) -> None:
        with patch("phantex.wte.engine.subprocess.run", side_effect=FileNotFoundError):
            records, warning = scan_wifi()
        assert records == []
        assert warning is not None
        assert "nmcli" in warning.lower()

    def test_returns_warning_on_permission_error(self) -> None:
        with patch("phantex.wte.engine.subprocess.run", side_effect=PermissionError):
            records, warning = scan_wifi()
        assert records == []
        assert warning is not None
        assert "permission" in warning.lower()

    def test_returns_warning_on_timeout(self) -> None:
        import subprocess as _subprocess

        with patch(
            "phantex.wte.engine.subprocess.run",
            side_effect=_subprocess.TimeoutExpired(cmd="nmcli", timeout=15),
        ):
            records, warning = scan_wifi()
        assert records == []
        assert warning is not None
        assert "timed out" in warning.lower()

    def test_returns_warning_on_nonzero_returncode(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: no wifi device"
        with patch("phantex.wte.engine.subprocess.run", return_value=mock_result):
            records, warning = scan_wifi()
        assert records == []
        assert warning is not None
        assert "failed" in warning.lower()

    def test_parses_nmcli_output(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "HomeNetwork:AA\\:BB\\:CC\\:DD\\:EE\\:FF:6:80:WPA2\n"
        mock_result.stderr = ""
        with patch("phantex.wte.engine.subprocess.run", return_value=mock_result):
            records, warning = scan_wifi()
        assert warning is None
        assert len(records) == 1
        assert records[0].bssid == "AA:BB:CC:DD:EE:FF"
        assert records[0].ssid == "HomeNetwork"
        assert records[0].channel == 6
        assert records[0].signal == 80
        assert records[0].security == "WPA2"

    def test_hidden_ssid_rendered_as_placeholder(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ":AA\\:BB\\:CC\\:DD\\:EE\\:01:11:60:WPA2\n"
        mock_result.stderr = ""
        with patch("phantex.wte.engine.subprocess.run", return_value=mock_result):
            records, warning = scan_wifi()
        assert warning is None
        assert len(records) == 1
        assert records[0].ssid == "[hidden]"

    def test_deduplicates_bssid(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        # Same BSSID appears twice (can happen with dual-band APs on same BSSID)
        mock_result.stdout = (
            "NetA:AA\\:BB\\:CC\\:DD\\:EE\\:FF:1:70:WPA2\n"
            "NetA:AA\\:BB\\:CC\\:DD\\:EE\\:FF:6:65:WPA2\n"
        )
        mock_result.stderr = ""
        with patch("phantex.wte.engine.subprocess.run", return_value=mock_result):
            records, warning = scan_wifi()
        assert len(records) == 1

    def test_skips_malformed_lines(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "incomplete\nNetB:BB\\:BB\\:BB\\:BB\\:BB\\:BB:36:55:OPEN\n"
        mock_result.stderr = ""
        with patch("phantex.wte.engine.subprocess.run", return_value=mock_result):
            records, warning = scan_wifi()
        assert len(records) == 1
        assert records[0].bssid == "BB:BB:BB:BB:BB:BB"
