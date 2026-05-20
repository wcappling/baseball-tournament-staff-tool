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


def test_native_login_matches_team_slug_case_insensitively_and_preserves_slug(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    with sqlite3.connect(tmp_path / "baseball_staff_tool.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        # Slugs are normalized to lowercase on creation; "8U_EBC" is stored as "8u_ebc".
        storage.create_team(conn, slug="8U_EBC", display_name="8U Easley Baseball Club", password="EBC")

    with TestClient(app) as client:
        login = client.post("/api/v1/login", json={"team_slug": "8u_ebc", "password": "EBC"})

        assert login.status_code == 200
        assert login.json()["team"]["slug"] == "8u_ebc"


def test_known_team_settings_include_brand_theme_defaults() -> None:
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        ebc = storage.create_team(conn, slug="8U_EBC", display_name="8U Easley Baseball Club", password="EBC")
        cove = storage.create_team(conn, slug="Cove_Crushers", display_name="9U Cove Crushers", password="cove")

        ebc_settings = storage.get_team_settings(conn, ebc["id"])
        cove_settings = storage.get_team_settings(conn, cove["id"])

        assert ebc_settings["brand_primary"] == "#050505"
        assert ebc_settings["brand_secondary"] == "#d8c27a"
        assert ebc_settings["logo_url"] == "/static/team-assets/ebc-logo.png"
        assert cove_settings["brand_primary"] == "#0b2b4f"
        assert cove_settings["brand_secondary"] == "#be174d"
        assert cove_settings["logo_url"] == "/static/team-assets/cove-crushers-mark.jpg"


def test_init_db_seeds_known_team_branding_for_existing_teams() -> None:
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        team = storage.create_team(
            conn,
            slug="Cove_Crushers",
            display_name="9U Cove Crushers",
            password="cove",
            settings={"brand_primary": "#123456", "logo_url": ""},
        )
        conn.execute("DELETE FROM team_settings WHERE team_id = ? AND key IN ('brand_primary', 'brand_secondary', 'brand_accent', 'logo_url')", (team["id"],))
        conn.commit()

        init_db(conn)
        settings = storage.get_team_settings(conn, team["id"])

        assert settings["brand_primary"] == "#0b2b4f"
        assert settings["logo_url"] == "/static/team-assets/cove-crushers-mark.jpg"


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


def test_v1_team_stats_family_requires_bearer_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    with sqlite3.connect(tmp_path / "baseball_staff_tool.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)

    with TestClient(app) as client:
        for path in ("/api/v1/team-stats", "/api/v1/team-analysis", "/api/v1/available-seasons"):
            response = client.get(path)
            assert response.status_code == 401, path
            assert response.json()["error"]["code"] == "authentication_required"


def test_v1_team_stats_family_scopes_to_bearer_team(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    with sqlite3.connect(tmp_path / "baseball_staff_tool.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        storage.create_team(
            conn,
            slug="8u-hawks",
            display_name="8U Hawks",
            password="eight-pass",
            settings={"target_age_division": "8U"},
        )
        storage.create_team(
            conn,
            slug="9u-hawks",
            display_name="9U Hawks",
            password="nine-pass",
            settings={"target_age_division": "9U"},
        )

    with TestClient(app) as client:
        eight_token = client.post(
            "/api/v1/login", json={"team_slug": "8u-hawks", "password": "eight-pass"}
        ).json()["session"]["token"]
        nine_token = client.post(
            "/api/v1/login", json={"team_slug": "9u-hawks", "password": "nine-pass"}
        ).json()["session"]["token"]

        eight_stats = client.get(
            "/api/v1/team-stats", headers={"Authorization": f"Bearer {eight_token}"}
        )
        assert eight_stats.status_code == 200
        body = eight_stats.json()
        assert body["age"] == "8U"
        assert "season" in body
        assert "teams" in body and isinstance(body["teams"], list)
        assert body["total_teams"] == len(body["teams"])

        nine_stats = client.get(
            "/api/v1/team-stats", headers={"Authorization": f"Bearer {nine_token}"}
        )
        assert nine_stats.status_code == 200
        assert nine_stats.json()["age"] == "9U"

        eight_stats_override = client.get(
            "/api/v1/team-stats",
            params={"age": "10U"},
            headers={"Authorization": f"Bearer {eight_token}"},
        )
        assert eight_stats_override.status_code == 200
        assert eight_stats_override.json()["age"] == "10U"

        eight_analysis = client.get(
            "/api/v1/team-analysis",
            headers={"Authorization": f"Bearer {eight_token}"},
        )
        assert eight_analysis.status_code == 200

        seasons = client.get(
            "/api/v1/available-seasons",
            headers={"Authorization": f"Bearer {eight_token}"},
        )
        assert seasons.status_code == 200
        seasons_body = seasons.json()
        assert "seasons" in seasons_body
        assert "current" in seasons_body


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


def test_web_team_login_matches_team_slug_case_insensitively(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAFF_TOOL_PASSWORD", "legacy-web-pass")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    with sqlite3.connect(tmp_path / "baseball_staff_tool.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        storage.create_team(
            conn,
            slug="Cove_Crushers",
            display_name="9U Cove Crushers",
            password="cove",
            settings={"target_age_division": "9U"},
        )

    with TestClient(app) as client:
        login = client.post(
            "/login",
            data={"team_slug": "cove_crushers", "password": "cove"},
            follow_redirects=False,
        )

        assert login.status_code == 303
        assert client.get("/api/settings").json()["target_age_division"] == "9U"


def test_web_settings_include_team_identity_for_branding(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAFF_TOOL_PASSWORD", "legacy-web-pass")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-that-is-long-enough")
    with sqlite3.connect(tmp_path / "baseball_staff_tool.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        # Slugs are normalized to lowercase on creation; "8U_EBC" is stored as "8u_ebc".
        storage.create_team(conn, slug="8U_EBC", display_name="8U Easley Baseball Club", password="EBC")

    with TestClient(app) as client:
        login = client.post("/login", data={"team_slug": "8u_ebc", "password": "EBC"}, follow_redirects=False)
        settings = client.get("/api/settings").json()

        assert login.status_code == 303
        assert settings["team_slug"] == "8u_ebc"
        assert settings["team_display_name"] == "8U Easley Baseball Club"
        assert settings["logo_url"] == "/static/team-assets/ebc-logo.png"


def test_web_login_page_has_team_code_field(monkeypatch) -> None:
    monkeypatch.setenv("STAFF_TOOL_PASSWORD", "legacy-web-pass")

    with TestClient(app) as client:
        page = client.get("/login")

    assert page.status_code == 200
    assert 'name="team_slug"' in page.text
    assert "Team code" in page.text


def test_static_ui_supports_team_branding() -> None:
    static_dir = Path(__file__).resolve().parents[1] / "static"
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    js = (static_dir / "app.js").read_text(encoding="utf-8")
    css = (static_dir / "styles.css").read_text(encoding="utf-8")

    assert 'id="teamLogo"' in html
    assert 'id="teamName"' in html
    assert "applyTeamBrand" in js
    assert "teamThemeTokens" in js
    assert "currentTeamSettings" in js
    assert "--brand-primary" in css
    assert "--brand-secondary" in css
    for token in ("--page", "--surface", "--panel", "--input-bg", "--link", "--line"):
        assert f'"{token}"' in js
    assert (static_dir / "team-assets" / "ebc-logo.png").exists()
    assert (static_dir / "team-assets" / "cove-crushers-mark.jpg").exists()


def test_static_ui_defaults_start_date_to_today() -> None:
    js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")

    assert "todayLocalDateValue" in js
    assert "setDefaultDateFilters" in js
    assert "startDateFilter.value = todayLocalDateValue()" in js
    assert "setDefaultDateFilters();" in js


def test_mobile_css_keeps_staff_workflows_visible() -> None:
    css = (Path(__file__).resolve().parents[1] / "static" / "styles.css").read_text(encoding="utf-8")

    hidden_block = re.compile(
        r"td:nth-child\((1|8|9|10|11)\)[^{]*\{[^}]*display:\s*none",
        re.MULTILINE,
    )
    assert hidden_block.search(css) is None
    assert "tr.team-details-row {\n    display: none" not in css
