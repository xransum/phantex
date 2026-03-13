"""Tests for phantex.bt.history -- upsert, get, count, clear."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask import Flask

from phantex.app import create_app
from phantex.bt.engine import DeviceRecord
from phantex.bt.history import (
    clear_history,
    get_history,
    get_history_count,
    upsert_device,
)
from phantex.db import close_db, init_db


def _make_record(
    mac: str = "AA:BB:CC:DD:EE:FF",
    name: str = "TestDevice",
    device_type: str = "BLE",
    rssi: int | None = -65,
    device_class: str | None = None,
    first_seen: datetime | None = None,
    last_seen: datetime | None = None,
) -> DeviceRecord:
    now = datetime.now(tz=UTC)
    return DeviceRecord(
        mac=mac,
        name=name,
        device_type=device_type,
        rssi=rssi,
        device_class=device_class,
        first_seen=first_seen or now,
        last_seen=last_seen or now,
    )


@pytest.fixture()
def app(tmp_path: Path):  # type: ignore[return]
    flask_app = create_app("phantex.settings.TestingConfig")
    flask_app.config["DB_PATH"] = tmp_path / "history_test.db"
    init_db(flask_app)
    yield flask_app
    close_db()


@pytest.fixture(autouse=True)
def app_ctx(app: Flask):
    with app.app_context():
        # Start each test with a clean table.
        clear_history()
        yield


class TestUpsertDevice:
    def test_insert_new_device(self) -> None:
        upsert_device(_make_record("11:22:33:44:55:66"))
        assert get_history_count() == 1

    def test_upsert_updates_last_seen(self) -> None:
        t1 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=UTC)
        upsert_device(_make_record("AA:AA:AA:AA:AA:AA", first_seen=t1, last_seen=t1))
        upsert_device(_make_record("AA:AA:AA:AA:AA:AA", first_seen=t2, last_seen=t2))
        rows = get_history()
        assert len(rows) == 1
        assert rows[0]["last_seen"] == t2.isoformat()

    def test_upsert_preserves_first_seen(self) -> None:
        t1 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=UTC)
        upsert_device(_make_record("BB:BB:BB:BB:BB:BB", first_seen=t1, last_seen=t1))
        upsert_device(_make_record("BB:BB:BB:BB:BB:BB", first_seen=t2, last_seen=t2))
        rows = get_history()
        assert rows[0]["first_seen"] == t1.isoformat()

    def test_upsert_updates_name(self) -> None:
        mac = "CC:CC:CC:CC:CC:CC"
        upsert_device(_make_record(mac, name="OldName"))
        upsert_device(_make_record(mac, name="NewName"))
        rows = get_history()
        assert rows[0]["name"] == "NewName"

    def test_upsert_updates_rssi(self) -> None:
        mac = "DD:DD:DD:DD:DD:DD"
        upsert_device(_make_record(mac, rssi=-80))
        upsert_device(_make_record(mac, rssi=-50))
        rows = get_history()
        assert rows[0]["rssi"] == -50

    def test_multiple_devices(self) -> None:
        upsert_device(_make_record("11:11:11:11:11:11"))
        upsert_device(_make_record("22:22:22:22:22:22"))
        upsert_device(_make_record("33:33:33:33:33:33"))
        assert get_history_count() == 3


class TestGetHistory:
    def test_empty_returns_empty_list(self) -> None:
        assert get_history() == []

    def test_returns_list_of_dicts(self) -> None:
        upsert_device(_make_record())
        rows = get_history()
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict)

    def test_dict_has_expected_keys(self) -> None:
        upsert_device(_make_record())
        row = get_history()[0]
        assert set(row.keys()) == {
            "mac",
            "name",
            "device_type",
            "rssi",
            "device_class",
            "first_seen",
            "last_seen",
        }


class TestGetHistoryCount:
    def test_zero_when_empty(self) -> None:
        assert get_history_count() == 0

    def test_increments_with_new_devices(self) -> None:
        upsert_device(_make_record("AA:00:00:00:00:01"))
        upsert_device(_make_record("AA:00:00:00:00:02"))
        assert get_history_count() == 2

    def test_does_not_double_count_upsert(self) -> None:
        upsert_device(_make_record("FF:FF:FF:FF:FF:FF"))
        upsert_device(_make_record("FF:FF:FF:FF:FF:FF"))
        assert get_history_count() == 1


class TestClearHistory:
    def test_clear_empties_table(self) -> None:
        upsert_device(_make_record("11:11:11:11:11:11"))
        upsert_device(_make_record("22:22:22:22:22:22"))
        clear_history()
        assert get_history_count() == 0

    def test_clear_on_empty_table_is_safe(self) -> None:
        clear_history()
        assert get_history_count() == 0

    def test_insert_after_clear(self) -> None:
        upsert_device(_make_record("11:11:11:11:11:11"))
        clear_history()
        upsert_device(_make_record("22:22:22:22:22:22"))
        assert get_history_count() == 1
