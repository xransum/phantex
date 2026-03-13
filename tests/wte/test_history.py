"""Tests for phantex.wte.history -- upsert, get, count, clear."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask import Flask

from phantex.app import create_app
from phantex.db import close_db, init_db
from phantex.wte.engine import NetworkRecord
from phantex.wte.history import (
    clear_history,
    get_history,
    get_history_count,
    upsert_network,
)


def _make_record(
    bssid: str = "AA:BB:CC:DD:EE:FF",
    ssid: str = "TestNet",
    channel: int | None = 6,
    signal: int | None = 75,
    security: str | None = "WPA2",
    first_seen: datetime | None = None,
    last_seen: datetime | None = None,
) -> NetworkRecord:
    now = datetime.now(tz=UTC)
    return NetworkRecord(
        bssid=bssid,
        ssid=ssid,
        channel=channel,
        signal=signal,
        security=security,
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
        clear_history()
        yield


class TestUpsertNetwork:
    def test_insert_new_network(self) -> None:
        upsert_network(_make_record("11:22:33:44:55:66"))
        assert get_history_count() == 1

    def test_upsert_updates_last_seen(self) -> None:
        t1 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=UTC)
        upsert_network(_make_record("AA:AA:AA:AA:AA:AA", first_seen=t1, last_seen=t1))
        upsert_network(_make_record("AA:AA:AA:AA:AA:AA", first_seen=t2, last_seen=t2))
        rows = get_history()
        assert len(rows) == 1
        assert rows[0]["last_seen"] == t2.isoformat()

    def test_upsert_preserves_first_seen(self) -> None:
        t1 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        t2 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=UTC)
        upsert_network(_make_record("BB:BB:BB:BB:BB:BB", first_seen=t1, last_seen=t1))
        upsert_network(_make_record("BB:BB:BB:BB:BB:BB", first_seen=t2, last_seen=t2))
        rows = get_history()
        assert rows[0]["first_seen"] == t1.isoformat()

    def test_upsert_updates_ssid(self) -> None:
        bssid = "CC:CC:CC:CC:CC:CC"
        upsert_network(_make_record(bssid, ssid="OldSSID"))
        upsert_network(_make_record(bssid, ssid="NewSSID"))
        rows = get_history()
        assert rows[0]["ssid"] == "NewSSID"

    def test_upsert_updates_signal(self) -> None:
        bssid = "DD:DD:DD:DD:DD:DD"
        upsert_network(_make_record(bssid, signal=40))
        upsert_network(_make_record(bssid, signal=90))
        rows = get_history()
        assert rows[0]["signal"] == 90

    def test_multiple_networks(self) -> None:
        upsert_network(_make_record("11:11:11:11:11:11"))
        upsert_network(_make_record("22:22:22:22:22:22"))
        upsert_network(_make_record("33:33:33:33:33:33"))
        assert get_history_count() == 3


class TestGetHistory:
    def test_empty_returns_empty_list(self) -> None:
        assert get_history() == []

    def test_returns_list_of_dicts(self) -> None:
        upsert_network(_make_record())
        rows = get_history()
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict)

    def test_dict_has_expected_keys(self) -> None:
        upsert_network(_make_record())
        row = get_history()[0]
        assert set(row.keys()) == {
            "bssid",
            "ssid",
            "channel",
            "signal",
            "security",
            "first_seen",
            "last_seen",
        }


class TestGetHistoryCount:
    def test_zero_when_empty(self) -> None:
        assert get_history_count() == 0

    def test_increments_with_new_networks(self) -> None:
        upsert_network(_make_record("AA:00:00:00:00:01"))
        upsert_network(_make_record("AA:00:00:00:00:02"))
        assert get_history_count() == 2

    def test_does_not_double_count_upsert(self) -> None:
        upsert_network(_make_record("FF:FF:FF:FF:FF:FF"))
        upsert_network(_make_record("FF:FF:FF:FF:FF:FF"))
        assert get_history_count() == 1


class TestClearHistory:
    def test_clear_empties_table(self) -> None:
        upsert_network(_make_record("11:11:11:11:11:11"))
        upsert_network(_make_record("22:22:22:22:22:22"))
        clear_history()
        assert get_history_count() == 0

    def test_clear_on_empty_table_is_safe(self) -> None:
        clear_history()
        assert get_history_count() == 0

    def test_insert_after_clear(self) -> None:
        upsert_network(_make_record("11:11:11:11:11:11"))
        clear_history()
        upsert_network(_make_record("22:22:22:22:22:22"))
        assert get_history_count() == 1
