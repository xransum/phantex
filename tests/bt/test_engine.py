"""Tests for the BT scanner engine."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from phantex.bt.engine import (
    DeviceRecord,
    _device_store,
    _merge_records,
    _store_lock,
    get_store_snapshot,
    scan_classic,
)


@pytest.fixture(autouse=True)
def clear_store() -> None:
    """Reset the shared device store before each test."""
    with _store_lock:
        _device_store.clear()


def make_record(mac: str = "AA:BB:CC:DD:EE:FF", device_type: str = "BLE") -> DeviceRecord:
    now = datetime.now(tz=UTC)
    return DeviceRecord(
        mac=mac,
        name="TestDevice",
        device_type=device_type,
        rssi=-70,
        device_class=None,
        first_seen=now,
        last_seen=now,
    )


class TestDeviceRecord:
    def test_to_dict_contains_expected_keys(self) -> None:
        record = make_record()
        d = record.to_dict()
        assert set(d.keys()) == {
            "mac",
            "name",
            "device_type",
            "rssi",
            "device_class",
            "first_seen",
            "last_seen",
        }

    def test_to_dict_iso_timestamps(self) -> None:
        record = make_record()
        d = record.to_dict()
        # Should be parseable ISO strings
        datetime.fromisoformat(str(d["first_seen"]))
        datetime.fromisoformat(str(d["last_seen"]))


class TestMergeRecords:
    def test_new_record_added_to_store(self) -> None:
        record = make_record("AA:BB:CC:DD:EE:01")
        _merge_records([record])
        snapshot, _, _ = get_store_snapshot()
        assert any(d.mac == "AA:BB:CC:DD:EE:01" for d in snapshot)

    def test_first_seen_preserved_on_update(self) -> None:
        original_time = datetime(2024, 1, 1, tzinfo=UTC)
        record = make_record("AA:BB:CC:DD:EE:02")
        record.first_seen = original_time
        _merge_records([record])

        # Simulate a second scan with a newer timestamp
        updated = make_record("AA:BB:CC:DD:EE:02")
        _merge_records([updated])

        snapshot, _, _ = get_store_snapshot()
        stored = next(d for d in snapshot if d.mac == "AA:BB:CC:DD:EE:02")
        assert stored.first_seen == original_time

    def test_multiple_records_merged(self) -> None:
        records = [make_record(f"AA:BB:CC:DD:EE:{i:02X}") for i in range(5)]
        _merge_records(records)
        snapshot, _, _ = get_store_snapshot()
        assert len(snapshot) == 5


class TestGetStoreSnapshot:
    def test_returns_empty_list_initially(self) -> None:
        devices, last_scan, warning = get_store_snapshot()
        assert devices == []
        assert last_scan is None
        assert warning is None

    def test_returns_copy_not_reference(self) -> None:
        _merge_records([make_record("AA:BB:CC:DD:EE:FF")])
        snapshot1, _, _ = get_store_snapshot()
        snapshot1.clear()
        snapshot2, _, _ = get_store_snapshot()
        # Original store should be unaffected
        assert len(snapshot2) == 1


class TestScanClassic:
    def test_returns_empty_list_and_warning_when_hcitool_missing(self) -> None:
        with patch("phantex.bt.engine.subprocess.run", side_effect=FileNotFoundError):
            records, warning = scan_classic()
        assert records == []
        assert warning is not None
        assert "hcitool" in warning.lower()

    def test_returns_warning_on_permission_error(self) -> None:
        with patch("phantex.bt.engine.subprocess.run", side_effect=PermissionError):
            records, warning = scan_classic()
        assert records == []
        assert warning is not None
        assert "permission" in warning.lower()

    def test_parses_hcitool_output(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Scanning ...\n\tAA:BB:CC:DD:EE:FF\tMyPhone\n"
        mock_result.stderr = ""
        with patch("phantex.bt.engine.subprocess.run", return_value=mock_result):
            records, warning = scan_classic()
        assert warning is None
        assert len(records) == 1
        assert records[0].mac == "AA:BB:CC:DD:EE:FF"
        assert records[0].name == "MyPhone"
        assert records[0].device_type == "Classic"
