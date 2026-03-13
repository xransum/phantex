"""Tests for phantex.db -- init_db, get_db, close_db."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from phantex.app import create_app
from phantex.db import close_db, get_db, init_db


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def app(tmp_db_path: Path):  # type: ignore[return]
    flask_app = create_app("phantex.settings.TestingConfig")
    # Override BEFORE calling init_db so the schema lands in the temp file.
    flask_app.config["DB_PATH"] = tmp_db_path
    init_db(flask_app)
    yield flask_app
    close_db()


class TestInitDb:
    def test_creates_db_file(self, app: Flask, tmp_db_path: Path) -> None:
        assert tmp_db_path.exists()

    def test_creates_bt_history_table(self, app: Flask, tmp_db_path: Path) -> None:
        conn = sqlite3.connect(str(tmp_db_path))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='bt_history'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c" / "phantex.db"
        flask_app = create_app("phantex.settings.TestingConfig")
        flask_app.config["DB_PATH"] = nested
        # init_db is called in create_app; but we reconfigured after -- call manually
        init_db(flask_app)
        assert nested.exists()

    def test_idempotent(self, app: Flask, tmp_db_path: Path) -> None:
        """Calling init_db a second time should not raise or corrupt the DB."""
        init_db(app)
        conn = sqlite3.connect(str(tmp_db_path))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='bt_history'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None


class TestGetDb:
    def test_returns_connection(self, app: Flask) -> None:
        with app.app_context():
            conn = get_db(app)
            assert isinstance(conn, sqlite3.Connection)

    def test_same_connection_in_same_thread(self, app: Flask) -> None:
        with app.app_context():
            c1 = get_db(app)
            c2 = get_db(app)
            assert c1 is c2

    def test_row_factory_set(self, app: Flask) -> None:
        with app.app_context():
            conn = get_db(app)
            assert conn.row_factory is sqlite3.Row


class TestCloseDb:
    def test_close_discards_connection(self, app: Flask) -> None:
        with app.app_context():
            conn = get_db(app)
            assert conn is not None
            close_db()
            # After closing, get_db should return a fresh connection
            conn2 = get_db(app)
            assert conn2 is not conn
