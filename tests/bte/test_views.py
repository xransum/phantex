"""Tests for the BTE blueprint views (/bte and /bte/data)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from flask import Flask
from flask.testing import FlaskClient

from phantex.app import create_app
from phantex.bte.engine import DeviceRecord, _device_store, _store_lock


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


class TestBTEIndex:
    def test_get_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/bte/")
        assert response.status_code == 200

    def test_response_contains_bte_title(self, client: FlaskClient) -> None:
        response = client.get("/bte/")
        assert b"BLUETOOTH TERMINAL EXPLORER" in response.data

    def test_response_contains_table(self, client: FlaskClient) -> None:
        response = client.get("/bte/")
        assert b"bte-table" in response.data


class TestBTEData:
    def test_get_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/bte/data")
        assert response.status_code == 200

    def test_response_is_json(self, client: FlaskClient) -> None:
        response = client.get("/bte/data")
        assert response.content_type == "application/json"

    def test_empty_store_returns_empty_devices(self, client: FlaskClient) -> None:
        response = client.get("/bte/data")
        data = json.loads(response.data)
        assert data["devices"] == []
        assert data["scan_warning"] is None
        assert data["last_scan"] is None

    def test_returns_devices_from_store(self, client: FlaskClient) -> None:
        record = make_record("11:22:33:44:55:66")
        with _store_lock:
            _device_store[record.mac] = record

        response = client.get("/bte/data")
        data = json.loads(response.data)
        assert len(data["devices"]) == 1
        assert data["devices"][0]["mac"] == "11:22:33:44:55:66"
        assert data["devices"][0]["device_type"] == "BLE"

    def test_device_dict_shape(self, client: FlaskClient) -> None:
        record = make_record()
        with _store_lock:
            _device_store[record.mac] = record

        response = client.get("/bte/data")
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
        import phantex.bte.engine as engine

        engine._scan_warning = "Classic BT unavailable: test"
        try:
            response = client.get("/bte/data")
            data = json.loads(response.data)
            assert data["scan_warning"] == "Classic BT unavailable: test"
        finally:
            engine._scan_warning = None
