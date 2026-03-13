"""Tests for the BT blueprint views (/bt and /bt/data)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from phantex.app import create_app
from phantex.bt.engine import DeviceRecord, _device_store, _store_lock
from phantex.bt.history import upsert_device
from phantex.db import init_db


@pytest.fixture()
def app() -> Flask:
    return create_app("phantex.settings.TestingConfig")


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture(autouse=True)
def clear_store() -> None:
    with _store_lock:
        _device_store.clear()


@pytest.fixture()
def history_app(tmp_path: Path):  # type: ignore[return]
    """App fixture with an isolated temp DB for history endpoint tests."""
    from phantex.db import close_db

    flask_app = create_app("phantex.settings.TestingConfig")
    flask_app.config["DB_PATH"] = tmp_path / "views_test.db"
    init_db(flask_app)
    yield flask_app
    # Close thread-local connection so the next test gets a fresh one.
    close_db()


@pytest.fixture()
def history_client(history_app: Flask) -> FlaskClient:
    return history_app.test_client()


@pytest.fixture()
def clean_history(history_app: Flask) -> None:
    """Ensure the history table is empty before each test that uses it."""
    from phantex.bt.history import clear_history

    with history_app.app_context():
        clear_history()


def make_record(mac: str = "AA:BB:CC:DD:EE:FF") -> DeviceRecord:
    now = datetime.now(tz=UTC)
    return DeviceRecord(
        mac=mac,
        name="TestDevice",
        device_type="BLE",
        rssi=-65,
        device_class=None,
        first_seen=now,
        last_seen=now,
    )


class TestBTIndex:
    def test_get_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/bt/")
        assert response.status_code == 200

    def test_response_contains_bt_title(self, client: FlaskClient) -> None:
        response = client.get("/bt/")
        assert b"BLUETOOTH SCANNER" in response.data

    def test_response_contains_table(self, client: FlaskClient) -> None:
        response = client.get("/bt/")
        assert b"bt-table" in response.data


class TestBTData:
    def test_get_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/bt/data")
        assert response.status_code == 200

    def test_response_is_json(self, client: FlaskClient) -> None:
        response = client.get("/bt/data")
        assert response.content_type == "application/json"

    def test_empty_store_returns_empty_devices(self, client: FlaskClient) -> None:
        response = client.get("/bt/data")
        data = json.loads(response.data)
        assert data["devices"] == []
        assert data["scan_warning"] is None
        assert data["last_scan"] is None

    def test_returns_devices_from_store(self, client: FlaskClient) -> None:
        record = make_record("11:22:33:44:55:66")
        with _store_lock:
            _device_store[record.mac] = record

        response = client.get("/bt/data")
        data = json.loads(response.data)
        assert len(data["devices"]) == 1
        assert data["devices"][0]["mac"] == "11:22:33:44:55:66"
        assert data["devices"][0]["device_type"] == "BLE"

    def test_device_dict_shape(self, client: FlaskClient) -> None:
        record = make_record()
        with _store_lock:
            _device_store[record.mac] = record

        response = client.get("/bt/data")
        data = json.loads(response.data)
        device = data["devices"][0]
        assert set(device.keys()) == {
            "mac",
            "name",
            "device_type",
            "rssi",
            "device_class",
            "first_seen",
            "last_seen",
        }

    def test_returns_scan_warning_when_set(self, client: FlaskClient) -> None:
        import phantex.bt.engine as engine

        engine._scan_warning = "Classic BT unavailable: test"
        try:
            response = client.get("/bt/data")
            data = json.loads(response.data)
            assert data["scan_warning"] == "Classic BT unavailable: test"
        finally:
            engine._scan_warning = None


class TestBTHistory:
    def test_get_returns_200(self, history_client: FlaskClient) -> None:
        response = history_client.get("/bt/history")
        assert response.status_code == 200

    def test_get_returns_json(self, history_client: FlaskClient) -> None:
        response = history_client.get("/bt/history")
        assert response.content_type == "application/json"

    def test_get_empty_returns_empty_devices(self, history_client: FlaskClient) -> None:
        response = history_client.get("/bt/history")
        data = json.loads(response.data)
        assert data["devices"] == []
        assert data["total"] == 0

    def test_get_returns_inserted_device(
        self, history_app: Flask, history_client: FlaskClient
    ) -> None:
        now = datetime.now(tz=UTC)
        record = DeviceRecord(
            mac="AA:BB:CC:DD:EE:FF",
            name="HistoryDevice",
            device_type="BLE",
            rssi=-70,
            device_class=None,
            first_seen=now,
            last_seen=now,
        )
        with history_app.app_context():
            upsert_device(record)

        response = history_client.get("/bt/history")
        data = json.loads(response.data)
        assert data["total"] == 1
        assert data["devices"][0]["mac"] == "AA:BB:CC:DD:EE:FF"
        assert data["devices"][0]["name"] == "HistoryDevice"

    def test_get_row_has_expected_keys(
        self, history_app: Flask, history_client: FlaskClient
    ) -> None:
        now = datetime.now(tz=UTC)
        record = DeviceRecord(
            mac="11:22:33:44:55:66",
            name="KeyTest",
            device_type="CLASSIC",
            rssi=None,
            device_class="0x200404",
            first_seen=now,
            last_seen=now,
        )
        with history_app.app_context():
            upsert_device(record)

        response = history_client.get("/bt/history")
        row = json.loads(response.data)["devices"][0]
        assert set(row.keys()) == {
            "mac",
            "name",
            "device_type",
            "rssi",
            "device_class",
            "first_seen",
            "last_seen",
        }


class TestBTHistoryClear:
    def test_post_returns_200(self, history_client: FlaskClient) -> None:
        response = history_client.post("/bt/history/clear")
        assert response.status_code == 200

    def test_post_returns_json(self, history_client: FlaskClient) -> None:
        response = history_client.post("/bt/history/clear")
        assert response.content_type == "application/json"

    def test_post_clears_all_rows(self, history_app: Flask, history_client: FlaskClient) -> None:
        now = datetime.now(tz=UTC)
        for mac in ("11:11:11:11:11:11", "22:22:22:22:22:22"):
            r = DeviceRecord(
                mac=mac,
                name="Dev",
                device_type="BLE",
                rssi=-60,
                device_class=None,
                first_seen=now,
                last_seen=now,
            )
            with history_app.app_context():
                upsert_device(r)

        history_client.post("/bt/history/clear")

        response = history_client.get("/bt/history")
        data = json.loads(response.data)
        assert data["devices"] == []
        assert data["total"] == 0

    def test_post_returns_ok(self, history_client: FlaskClient) -> None:
        data = json.loads(history_client.post("/bt/history/clear").data)
        assert data.get("ok") is True
