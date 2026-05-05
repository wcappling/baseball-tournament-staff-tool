from __future__ import annotations

import sqlite3
import re
from pathlib import Path

from fastapi.testclient import TestClient

from baseball_aggregator import storage
from baseball_aggregator.app import app
from baseball_aggregator.models import Tournament
from baseball_aggregator.storage import (
    init_db,
    search_tournaments,
    upsert_shortlist,
    upsert_tournaments,
)


def test_team_settings_and_shortlist_state_are_isolated() -> None:
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        eight = storage.create_team(
            conn,
            slug="8u-hawks",
            display_name="8U Hawks",
            password="eight-pass",
            settings={"target_age_division": "8U", "radius_miles": 100},
        )
        nine = storage.create_team(
            conn,
            slug="9u-hawks",
            display_name="9U Hawks",
            password="nine-pass",
            settings={"target_age_division": "9U", "radius_miles": 200},
        )
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="shared",
                    name="Shared Tournament",
                    detail_url="https://example.com/shared",
                    location="Madison, AL",
                    age_divisions=["8U", "8U OPEN", "9U", "9U AA"],
                    registered_teams=10,
                    division_team_counts={"8U OPEN": 4, "9U AA": 6},
                    team_count_scope="division",
                )
            ],
        )
        tournament_id = conn.execute("SELECT id FROM tournaments WHERE source_id = 'shared'").fetchone()["id"]

        upsert_shortlist(conn, tournament_id, {"status": "Interested", "notes": "8U note"}, team_id=eight["id"])
        upsert_shortlist(conn, tournament_id, {"status": "Declined", "notes": "9U note"}, team_id=nine["id"])

        eight_rows = search_tournaments(conn, {}, team_id=eight["id"])
        nine_rows = search_tournaments(conn, {}, team_id=nine["id"])

        assert storage.get_team_settings(conn, eight["id"])["target_age_division"] == "8U"
        assert storage.get_team_settings(conn, nine["id"])["target_age_division"] == "9U"
        assert eight_rows[0]["shortlist_status"] == "Interested"
        assert eight_rows[0]["shortlist_notes"] == "8U note"
        assert eight_rows[0]["target_age_division"] == "8U"
        assert nine_rows[0]["shortlist_status"] == "Declined"
        assert nine_rows[0]["shortlist_notes"] == "9U note"
        assert nine_rows[0]["target_age_division"] == "9U"


def test_existing_single_team_data_migrates_to_default_team() -> None:
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                name TEXT NOT NULL,
                detail_url TEXT NOT NULL,
                age_divisions TEXT NOT NULL DEFAULT '[]',
                fetched_at TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(source, source_id)
            );
            CREATE TABLE shortlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'Watch',
                priority INTEGER NOT NULL DEFAULT 3,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO settings(key, value) VALUES
                ('target_age_division', '"9U"'),
                ('radius_miles', '100');
            INSERT INTO tournaments(source, source_id, name, detail_url, fetched_at, first_seen_at, last_seen_at)
            VALUES ('ncs', 'legacy', 'Legacy Event', 'https://example.com', '2026-01-01', '2026-01-01', '2026-01-01');
            INSERT INTO shortlist(tournament_id, status, priority, notes, created_at, updated_at)
            VALUES (1, 'Registered', 2, 'legacy note', '2026-01-01', '2026-01-01');
            """
        )

        init_db(conn)
        team = storage.get_default_team(conn)
        rows = search_tournaments(conn, {}, team_id=team["id"])

        assert team["slug"] == "default"
        assert storage.get_team_settings(conn, team["id"])["target_age_division"] == "9U"
        assert rows[0]["shortlist_status"] == "Registered"
        assert rows[0]["shortlist_notes"] == "legacy note"


def test_native_login_and_v1_api_are_team_scoped(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    with sqlite3.connect(tmp_path / "baseball_staff_tool.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        storage.create_team(conn, slug="8u-hawks", display_name="8U Hawks", password="eight-pass")
        storage.create_team(conn, slug="9u-hawks", display_name="9U Hawks", password="nine-pass")

    with TestClient(app) as client:
        bad = client.post("/api/v1/login", json={"team_slug": "8u-hawks", "password": "wrong"})
        assert bad.status_code == 401
        assert bad.json() == {"error": {"code": "invalid_credentials", "message": "Invalid team login."}}

        login = client.post("/api/v1/login", json={"team_slug": "8u-hawks", "password": "eight-pass"})
        assert login.status_code == 200
        body = login.json()
        assert body["team"]["slug"] == "8u-hawks"
        assert body["session"]["token"]

        token = body["session"]["token"]
        settings = client.get("/api/v1/settings", headers={"Authorization": f"Bearer {token}"})
        assert settings.status_code == 200
        assert settings.json()["team"]["slug"] == "8u-hawks"

        me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["team"]["slug"] == "8u-hawks"

        logout = client.post("/api/v1/logout", headers={"Authorization": f"Bearer {token}"})
        assert logout.status_code == 200
        expired = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert expired.status_code == 401
        assert expired.json() == {"error": {"code": "invalid_session", "message": "Session is invalid or expired."}}


def test_native_bearer_auth_works_when_cookie_auth_is_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAFF_TOOL_PASSWORD", "legacy-web-pass")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    with sqlite3.connect(tmp_path / "baseball_staff_tool.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        storage.create_team(conn, slug="8u-hawks", display_name="8U Hawks", password="eight-pass")

    with TestClient(app) as client:
        login = client.post("/api/v1/login", json={"team_slug": "8u-hawks", "password": "eight-pass"})
        token = login.json()["session"]["token"]

        response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["team"]["slug"] == "8u-hawks"


def test_web_team_login_scopes_existing_browser_api(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAFF_TOOL_PASSWORD", "legacy-web-pass")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    with sqlite3.connect(tmp_path / "baseball_staff_tool.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        eight = storage.create_team(
            conn,
            slug="8u-hawks",
            display_name="8U Hawks",
            password="eight-pass",
            settings={"target_age_division": "8U", "radius_miles": 100},
        )
        nine = storage.create_team(
            conn,
            slug="9u-hawks",
            display_name="9U Hawks",
            password="nine-pass",
            settings={"target_age_division": "9U", "radius_miles": 150},
        )
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="web-shared",
                    name="Web Shared Tournament",
                    detail_url="https://example.com/shared",
                    location="Madison, AL",
                    age_divisions=["8U", "8U OPEN", "9U", "9U AA"],
                    registered_teams=10,
                    division_team_counts={"8U OPEN": 4, "9U AA": 6},
                    team_count_scope="division",
                )
            ],
        )
        tournament_id = conn.execute("SELECT id FROM tournaments WHERE source_id = 'web-shared'").fetchone()["id"]
        upsert_shortlist(conn, tournament_id, {"status": "Interested", "notes": "8U browser"}, team_id=eight["id"])
        upsert_shortlist(conn, tournament_id, {"status": "Declined", "notes": "9U browser"}, team_id=nine["id"])

    with TestClient(app) as eight_client:
        login = eight_client.post(
            "/login",
            data={"team_slug": "8u-hawks", "password": "eight-pass"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        settings = eight_client.get("/api/settings").json()
        assert settings["target_age_division"] == "8U"
        rows = eight_client.get("/api/tournaments").json()
        assert rows[0]["shortlist_status"] == "Interested"
        assert rows[0]["shortlist_notes"] == "8U browser"

    with TestClient(app) as nine_client:
        login = nine_client.post(
            "/login",
            data={"team_slug": "9u-hawks", "password": "nine-pass"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        settings = nine_client.get("/api/settings").json()
        assert settings["target_age_division"] == "9U"
        rows = nine_client.get("/api/tournaments").json()
        assert rows[0]["shortlist_status"] == "Declined"
        assert rows[0]["shortlist_notes"] == "9U browser"


def test_web_login_page_has_team_code_field(monkeypatch) -> None:
    monkeypatch.setenv("STAFF_TOOL_PASSWORD", "legacy-web-pass")

    with TestClient(app) as client:
        page = client.get("/login")

    assert page.status_code == 200
    assert 'name="team_slug"' in page.text
    assert "Team code" in page.text


def test_mobile_css_keeps_staff_workflows_visible() -> None:
    css = (Path(__file__).resolve().parents[1] / "static" / "styles.css").read_text(encoding="utf-8")

    hidden_block = re.compile(
        r"td:nth-child\((1|8|9|10|11)\)[^{]*\{[^}]*display:\s*none",
        re.MULTILINE,
    )
    assert hidden_block.search(css) is None
    assert "tr.team-details-row {\n    display: none" not in css
