from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from baseball_aggregator import auth
from baseball_aggregator import services
from baseball_aggregator.app import app
from baseball_aggregator.config import get_db_path, require_hosted_config
from baseball_aggregator.maintenance import create_sqlite_backup, prune_backups
from baseball_aggregator.storage import connect, init_db


def test_auth_blocks_api_and_allows_login_and_static(monkeypatch):
    monkeypatch.setenv("STAFF_TOOL_PASSWORD", "staff-pass")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")

    with TestClient(app) as client:
        assert client.get("/api/settings").status_code == 401
        assert client.get("/static/styles.css").status_code == 200

        bad = client.post("/login", data={"password": "wrong"})
        assert bad.status_code == 200
        assert "did not match" in bad.text

        good = client.post("/login", data={"password": "admin-pass"}, follow_redirects=False)
        assert good.status_code == 303
        assert "baseball_staff_session" in good.headers["set-cookie"]

        response = client.get("/api/settings")
        assert response.status_code == 200


def test_auth_rejects_tampered_expired_and_future_cookies(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    valid = auth._sign_session(int(time.time()))
    assert auth._valid_session(valid) is True
    assert auth._valid_session(valid + "tampered") is False
    assert auth._valid_session(auth._sign_session(1)) is False
    assert auth._valid_session(auth._sign_session(9_999_999_999)) is False


def test_hosted_mode_requires_auth_secret_and_data_dir(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("STAFF_TOOL_PASSWORD", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.delenv("STAFF_TOOL_DATA_DIR", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    try:
        require_hosted_config()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Hosted mode should fail without required env vars")

    assert "STAFF_TOOL_PASSWORD" in message
    assert "SESSION_SECRET" in message
    assert "STAFF_TOOL_DATA_DIR" in message
    assert "ADMIN_PASSWORD" in message

    monkeypatch.setenv("STAFF_TOOL_PASSWORD", "staff-pass")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(Path("data")))
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass")
    require_hosted_config()


def test_db_path_honors_staff_tool_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    assert get_db_path() == tmp_path / "baseball_staff_tool.sqlite3"

    with connect() as conn:
        init_db(conn)
    assert (tmp_path / "baseball_staff_tool.sqlite3").exists()


def test_backup_creates_sqlite_copy_and_retains_seven(tmp_path):
    db_path = tmp_path / "baseball_staff_tool.sqlite3"
    backup_dir = tmp_path / "backups"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO sample(name) VALUES ('backup-check')")

    backup = create_sqlite_backup(db_path, backup_dir)
    assert backup is not None
    with sqlite3.connect(backup) as conn:
        row = conn.execute("SELECT name FROM sample").fetchone()
    assert row[0] == "backup-check"

    prune_dir = tmp_path / "prune-backups"
    for index in range(9):
        path = prune_dir / f"baseball_staff_tool-20260429-12000{index}.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fake backup", encoding="utf-8")
        timestamp = time.time() + index
        os.utime(path, (timestamp, timestamp))

    removed = prune_backups(prune_dir, keep=7)
    remaining = sorted(prune_dir.glob("baseball_staff_tool-*.sqlite3"))
    assert len(removed) == 2
    assert len(remaining) == 7

    assert create_sqlite_backup(tmp_path / "missing.sqlite3", backup_dir) is None
    sentinel = prune_dir / "do-not-delete.txt"
    sentinel.write_text("keep", encoding="utf-8")
    prune_backups(prune_dir, keep=1)
    assert sentinel.exists()


def test_refresh_lock_prevents_overlapping_runs():
    assert services._refresh_lock.acquire(blocking=False)
    try:
        assert services.refresh_sources() == {"status": "skipped", "message": "Refresh already running"}
    finally:
        services._refresh_lock.release()
