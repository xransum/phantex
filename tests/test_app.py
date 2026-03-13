"""Tests for the Flask application factory and top-level routes."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from phantex.app import create_app


@pytest.fixture()
def app() -> Flask:
    return create_app("phantex.settings.TestingConfig")


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


class TestCreateApp:
    def test_returns_flask_instance(self, app: Flask) -> None:
        assert isinstance(app, Flask)

    def test_testing_flag_set(self, app: Flask) -> None:
        assert app.testing is True

    def test_scheduler_not_started_in_testing(self, app: Flask) -> None:
        # Scheduler should not be registered in testing mode.
        assert "scheduler" not in app.extensions


class TestIndexRoute:
    def test_get_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_response_contains_phantex(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert b"PHANTEX" in response.data


class TestErrorHandlers:
    def test_404_returns_404(self, client: FlaskClient) -> None:
        response = client.get("/does-not-exist")
        assert response.status_code == 404

    def test_404_contains_error_text(self, client: FlaskClient) -> None:
        response = client.get("/does-not-exist")
        assert b"404" in response.data
