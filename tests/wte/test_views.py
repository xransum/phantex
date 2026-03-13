"""Tests for the WTE blueprint views (/wte and /wte/data)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from phantex.app import create_app
from phantex.db import init_db
from phantex.wte.engine import NetworkRecord, _network_store, _store_lock
from phantex.wte.history import upsert_network


@pytest.fixture()
def app() -> Flask:
    return create_app("phantex.settings.TestingConfig")


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture(autouse=True)
def clear_store() -> None:
    with _store_lock:
        _network_store.clear()


@pytest.fixture()
def history_app(tmp_path: Path):  # type: ignore[return]
    """App fixture with an isolated temp DB for history endpoint tests."""
    from phantex.db import close_db

    flask_app = create_app("phantex.settings.TestingConfig")
    flask_app.config["DB_PATH"] = tmp_path / "views_test.db"
    init_db(flask_app)
    yield flask_app
    close_db()


@pytest.fixture()
def history_client(history_app: Flask) -> FlaskClient:
    return history_app.test_client()


@pytest.fixture()
def clean_history(history_app: Flask) -> None:
    """Ensure the history table is empty before each test that uses it."""
    from phantex.wte.history import clear_history

    with history_app.app_context():
        clear_history()


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


class TestWTEIndex:
    def test_get_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/wte/")
        assert response.status_code == 200

    def test_response_contains_wte_title(self, client: FlaskClient) -> None:
        response = client.get("/wte/")
        assert b"WIRELESS TERMINAL EXPLORER" in response.data

    def test_response_contains_table(self, client: FlaskClient) -> None:
        response = client.get("/wte/")
        assert b"bt-table" in response.data


class TestWTEData:
    def test_get_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/wte/data")
        assert response.status_code == 200

    def test_response_is_json(self, client: FlaskClient) -> None:
        response = client.get("/wte/data")
        assert response.content_type == "application/json"

    def test_empty_store_returns_empty_networks(self, client: FlaskClient) -> None:
        response = client.get("/wte/data")
        data = json.loads(response.data)
        assert data["networks"] == []
        assert data["scan_warning"] is None
        assert data["last_scan"] is None

    def test_returns_networks_from_store(self, client: FlaskClient) -> None:
        record = make_record("11:22:33:44:55:66")
        with _store_lock:
            _network_store[record.bssid] = record

        response = client.get("/wte/data")
        data = json.loads(response.data)
        assert len(data["networks"]) == 1
        assert data["networks"][0]["bssid"] == "11:22:33:44:55:66"
        assert data["networks"][0]["ssid"] == "TestNet"

    def test_network_dict_shape(self, client: FlaskClient) -> None:
        record = make_record()
        with _store_lock:
            _network_store[record.bssid] = record

        response = client.get("/wte/data")
        data = json.loads(response.data)
        network = data["networks"][0]
        assert set(network.keys()) == {
            "bssid",
            "ssid",
            "channel",
            "signal",
            "security",
            "first_seen",
            "last_seen",
        }

    def test_returns_scan_warning_when_set(self, client: FlaskClient) -> None:
        import phantex.wte.engine as engine

        engine._scan_warning = "WiFi scan unavailable: test"
        try:
            response = client.get("/wte/data")
            data = json.loads(response.data)
            assert data["scan_warning"] == "WiFi scan unavailable: test"
        finally:
            engine._scan_warning = None


class TestWTEHistory:
    def test_get_returns_200(self, history_client: FlaskClient) -> None:
        response = history_client.get("/wte/history")
        assert response.status_code == 200

    def test_get_returns_json(self, history_client: FlaskClient) -> None:
        response = history_client.get("/wte/history")
        assert response.content_type == "application/json"

    def test_get_empty_returns_empty_networks(self, history_client: FlaskClient) -> None:
        response = history_client.get("/wte/history")
        data = json.loads(response.data)
        assert data["networks"] == []
        assert data["total"] == 0

    def test_get_returns_inserted_network(
        self, history_app: Flask, history_client: FlaskClient
    ) -> None:
        now = datetime.now(tz=UTC)
        record = NetworkRecord(
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="HistoryNet",
            channel=11,
            signal=60,
            security="WPA3",
            first_seen=now,
            last_seen=now,
        )
        with history_app.app_context():
            upsert_network(record)

        response = history_client.get("/wte/history")
        data = json.loads(response.data)
        assert data["total"] == 1
        assert data["networks"][0]["bssid"] == "AA:BB:CC:DD:EE:FF"
        assert data["networks"][0]["ssid"] == "HistoryNet"

    def test_get_row_has_expected_keys(
        self, history_app: Flask, history_client: FlaskClient
    ) -> None:
        now = datetime.now(tz=UTC)
        record = NetworkRecord(
            bssid="11:22:33:44:55:66",
            ssid="KeyTest",
            channel=36,
            signal=50,
            security=None,
            first_seen=now,
            last_seen=now,
        )
        with history_app.app_context():
            upsert_network(record)

        response = history_client.get("/wte/history")
        row = json.loads(response.data)["networks"][0]
        assert set(row.keys()) == {
            "bssid",
            "ssid",
            "channel",
            "signal",
            "security",
            "first_seen",
            "last_seen",
        }


class TestWTEHistoryClear:
    def test_post_returns_200(self, history_client: FlaskClient) -> None:
        response = history_client.post("/wte/history/clear")
        assert response.status_code == 200

    def test_post_returns_json(self, history_client: FlaskClient) -> None:
        response = history_client.post("/wte/history/clear")
        assert response.content_type == "application/json"

    def test_post_clears_all_rows(self, history_app: Flask, history_client: FlaskClient) -> None:
        now = datetime.now(tz=UTC)
        for bssid in ("11:11:11:11:11:11", "22:22:22:22:22:22"):
            r = NetworkRecord(
                bssid=bssid,
                ssid="Dev",
                channel=6,
                signal=70,
                security="WPA2",
                first_seen=now,
                last_seen=now,
            )
            with history_app.app_context():
                upsert_network(r)

        history_client.post("/wte/history/clear")

        response = history_client.get("/wte/history")
        data = json.loads(response.data)
        assert data["networks"] == []
        assert data["total"] == 0

    def test_post_returns_ok(self, history_client: FlaskClient) -> None:
        data = json.loads(history_client.post("/wte/history/clear").data)
        assert data.get("ok") is True
