from __future__ import annotations

import json
import logging
import os
import re
import secrets
import hashlib
import hmac
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from baseball_aggregator.config import get_db_path
from baseball_aggregator.distance import HUNTSVILLE, estimate_distance_miles, resolve_home_coords
from baseball_aggregator.models import DEFAULT_SETTINGS, Tournament

log = logging.getLogger(__name__)

_ALLOWED_TABLES: frozenset[str] = frozenset({
    "tournaments", "shortlist", "team_settings", "teams",
    "team_sessions", "team_records", "refresh_runs", "ncs_team_records",
    "team_stat_refresh",
})
_ALLOWED_COLUMN_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
_DIVISION_DETAIL_NOISE_FIELDS: frozenset[str] = frozenset({"pending_entries", "deadline_passed"})

_TOURNAMENT_COLUMNS: frozenset[str] = frozenset({
    "source", "source_id", "name", "detail_url", "location", "director",
    "start_date", "end_date", "age_divisions", "registered_teams",
    "division_team_counts", "division_confirmed_counts", "division_details",
    "division_teams", "team_count_scope", "stature", "format", "tags",
    "logo_url", "distance_miles", "fetched_at",
})

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = get_db_path()
TEAM_THEME_DEFAULTS = {
    "8u_ebc": {
        "brand_primary": "#050505",
        "brand_secondary": "#d8c27a",
        "brand_accent": "#ffffff",
        "logo_url": "/static/team-assets/ebc-logo.png",
    },
    "cove_crushers": {
        "brand_primary": "#0b2b4f",
        "brand_secondary": "#be174d",
        "brand_accent": "#ffffff",
        "logo_url": "/static/team-assets/cove-crushers-mark.jpg",
    },
}


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    db_path = db_path or get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    # Restrict file to owner-only after creation to prevent unintended reads.
    try:
        os.chmod(db_path, 0o600)
    except OSError:
        pass
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS team_settings (
            team_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY(team_id, key),
            FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS team_sessions (
            token_hash TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT NOT NULL,
            name TEXT NOT NULL,
            detail_url TEXT NOT NULL,
            location TEXT,
            director TEXT,
            start_date TEXT,
            end_date TEXT,
            age_divisions TEXT NOT NULL DEFAULT '[]',
            registered_teams INTEGER,
            division_team_counts TEXT NOT NULL DEFAULT '{}',
            division_confirmed_counts TEXT NOT NULL DEFAULT '{}',
            division_details TEXT NOT NULL DEFAULT '{}',
            division_teams TEXT NOT NULL DEFAULT '{}',
            team_count_scope TEXT NOT NULL DEFAULT 'event',
            stature TEXT,
            format TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            logo_url TEXT,
            distance_miles REAL,
            fetched_at TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(source, source_id)
        );

        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER,
            source TEXT NOT NULL,
            source_id TEXT NOT NULL,
            field TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            detected_at TEXT NOT NULL,
            staff_visible INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS refresh_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            tournaments_seen INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS team_records (
            id            INTEGER PRIMARY KEY,
            team_id       TEXT NOT NULL,
            source        TEXT NOT NULL,
            team_name     TEXT NOT NULL,
            age_division  TEXT,
            season        TEXT NOT NULL,
            wins          INTEGER NOT NULL DEFAULT 0,
            losses        INTEGER NOT NULL DEFAULT 0,
            ties          INTEGER NOT NULL DEFAULT 0,
            detail_url    TEXT,
            scraped_at    TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
            UNIQUE(team_id, source, team_name, season)
        );

        CREATE TABLE IF NOT EXISTS team_stat_refresh (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id          TEXT NOT NULL,
            source           TEXT NOT NULL,
            started_at       TEXT NOT NULL,
            finished_at      TEXT,
            status           TEXT NOT NULL,
            teams_refreshed  INTEGER NOT NULL DEFAULT 0,
            message          TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_team_stat_refresh_lookup
            ON team_stat_refresh(team_id, source, started_at DESC);
        """
    )
    _ensure_column(conn, "tournaments", "location", "TEXT")
    _ensure_column(conn, "tournaments", "director", "TEXT")
    _ensure_column(conn, "tournaments", "start_date", "TEXT")
    _ensure_column(conn, "tournaments", "end_date", "TEXT")
    _ensure_column(conn, "tournaments", "registered_teams", "INTEGER")
    _ensure_column(conn, "tournaments", "division_team_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "tournaments", "division_teams", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "tournaments", "division_confirmed_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "tournaments", "division_details", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "tournaments", "team_count_scope", "TEXT NOT NULL DEFAULT 'event'")
    _ensure_column(conn, "tournaments", "stature", "TEXT")
    _ensure_column(conn, "tournaments", "format", "TEXT")
    _ensure_column(conn, "tournaments", "tags", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(conn, "tournaments", "logo_url", "TEXT")
    _ensure_column(conn, "tournaments", "distance_miles", "REAL")
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )
    _ensure_default_team(conn)
    _migrate_shortlist_table(conn)
    _seed_known_team_theme_defaults(conn)
    _backfill_missing_distances(conn)
    _ensure_ncs_team_records_table(conn)
    _backfill_enabled_sources(conn)
    conn.commit()


def get_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    init_db(conn)
    return get_team_settings(conn, get_default_team(conn)["id"])


def update_settings(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    init_db(conn)
    return update_team_settings(conn, get_default_team(conn)["id"], payload)


def get_default_team(conn: sqlite3.Connection) -> dict[str, Any]:
    _ensure_default_team(conn)
    row = conn.execute("SELECT * FROM teams WHERE id = 'default'").fetchone()
    return dict(row)


def create_team(
    conn: sqlite3.Connection,
    *,
    slug: str,
    display_name: str,
    password: str | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db(conn)
    slug = slug.lower().strip()
    now = datetime.now(UTC).isoformat()
    team_id = slug if slug == "default" else uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO teams(id, slug, display_name, password_hash, active, created_at, updated_at)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            display_name = excluded.display_name,
            password_hash = COALESCE(excluded.password_hash, teams.password_hash),
            active = 1,
            updated_at = excluded.updated_at
        """,
        (team_id, slug, display_name, _hash_password(password) if password else None, now, now),
    )
    row = conn.execute("SELECT * FROM teams WHERE slug = ?", (slug,)).fetchone()
    team = dict(row)
    merged_settings = dict(DEFAULT_SETTINGS)
    merged_settings.update(TEAM_THEME_DEFAULTS.get(slug.casefold(), {}))
    merged_settings.update(settings or {})
    for key, value in merged_settings.items():
        if key in DEFAULT_SETTINGS:
            conn.execute(
                "INSERT OR IGNORE INTO team_settings(team_id, key, value) VALUES (?, ?, ?)",
                (team["id"], key, json.dumps(value)),
            )
    if settings:
        update_team_settings(conn, team["id"], settings)
    conn.commit()
    return team


def list_teams(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT id, slug, display_name, active, created_at, updated_at
        FROM teams
        ORDER BY slug
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_team_by_slug(conn: sqlite3.Connection, slug: str) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute("SELECT * FROM teams WHERE lower(slug) = lower(?) AND active = 1", (slug,)).fetchone()
    return dict(row) if row else None


def get_team_settings(conn: sqlite3.Connection, team_id: str) -> dict[str, Any]:
    values = dict(DEFAULT_SETTINGS)
    for row in conn.execute("SELECT key, value FROM team_settings WHERE team_id = ?", (team_id,)):
        values[row["key"]] = json.loads(row["value"])
    return values


def update_team_settings(conn: sqlite3.Connection, team_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db(conn)
    current = get_team_settings(conn, team_id)
    for key, value in payload.items():
        if key not in DEFAULT_SETTINGS:
            continue
        current[key] = value
        conn.execute(
            "INSERT INTO team_settings(team_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(team_id, key) DO UPDATE SET value = excluded.value",
            (team_id, key, json.dumps(value)),
        )
    conn.commit()
    return current


def update_team_password(conn: sqlite3.Connection, team_id: str, new_password: str) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE teams SET password_hash = ?, updated_at = ? WHERE id = ?",
        (_hash_password(new_password), now, team_id),
    )
    conn.commit()


def set_team_active(conn: sqlite3.Connection, team_id: str, active: bool) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE teams SET active = ?, updated_at = ? WHERE id = ?",
        (1 if active else 0, now, team_id),
    )
    conn.commit()


def delete_team(conn: sqlite3.Connection, team_id: str) -> None:
    if team_id == "default":
        raise ValueError("Cannot delete the default team.")
    conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    conn.commit()


def verify_team_password(conn: sqlite3.Connection, slug: str, password: str) -> dict[str, Any] | None:
    team = get_team_by_slug(conn, slug)
    if not team or not team.get("password_hash"):
        return None
    if _verify_password(password, team["password_hash"]):
        return team
    return None


def create_team_session(conn: sqlite3.Connection, team_id: str, max_age_seconds: int = 60 * 60 * 24 * 30) -> dict[str, Any]:
    init_db(conn)
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=max_age_seconds)
    conn.execute(
        "INSERT INTO team_sessions(token_hash, team_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_hash_token(token), team_id, now.isoformat(), expires_at.isoformat()),
    )
    conn.commit()
    log.info("Session created for team_id=%s expires=%s", team_id, expires_at.isoformat())
    return {"token": token, "created_at": now.isoformat(), "expires_at": expires_at.isoformat()}


def get_session_for_token(conn: sqlite3.Connection, token: str) -> dict[str, Any] | None:
    init_db(conn)
    row = conn.execute(
        """
        SELECT s.*, t.slug AS team_slug, t.display_name AS team_display_name, t.active AS team_active
        FROM team_sessions s
        JOIN teams t ON t.id = s.team_id
        WHERE s.token_hash = ?
        """,
        (_hash_token(token),),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    if data["revoked_at"] or not data["team_active"]:
        return None
    if datetime.fromisoformat(data["expires_at"]) <= datetime.now(UTC):
        return None
    return data


def revoke_team_session(conn: sqlite3.Connection, token: str) -> None:
    init_db(conn)
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE team_sessions SET revoked_at = ? WHERE token_hash = ?",
        (now, _hash_token(token)),
    )
    conn.commit()
    log.info("Session revoked at %s", now)


def prune_expired_sessions(conn: sqlite3.Connection) -> int:
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "DELETE FROM team_sessions WHERE expires_at <= ? OR revoked_at IS NOT NULL",
        (now,),
    )
    conn.commit()
    deleted = cursor.rowcount
    if deleted:
        log.info("Pruned %d expired/revoked session(s)", deleted)
    return deleted


def _division_details_has_meaningful_change(old_json: str | None, new_json: str | None) -> bool:
    """Return True only if division_details changed in a staff-relevant field (not just pending_entries etc.)."""
    try:
        old = json.loads(old_json or "{}")
        new = json.loads(new_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return True
    for div in set(old) | set(new):
        o = old.get(div) or {}
        n = new.get(div) or {}
        for key in set(o) | set(n):
            if key in _DIVISION_DETAIL_NOISE_FIELDS:
                continue
            if o.get(key) != n.get(key):
                return True
    return False


def upsert_tournaments(conn: sqlite3.Connection, tournaments: list[Tournament]) -> dict[str, int]:
    init_db(conn)
    inserted = 0
    updated = 0
    now = datetime.now(UTC).isoformat()
    tracked_fields = [
        "name",
        "start_date",
        "end_date",
        "location",
        "registered_teams",
        "division_team_counts",
        "division_confirmed_counts",
        "division_details",
        "division_teams",
        "stature",
    ]

    for tournament in tournaments:
        if not tournament.source_id:
            continue
        existing = conn.execute(
            "SELECT * FROM tournaments WHERE source = ? AND source_id = ?",
            (tournament.source, tournament.source_id),
        ).fetchone()
        payload = _tournament_payload(tournament)
        assert set(payload.keys()) <= _TOURNAMENT_COLUMNS, f"Unexpected tournament columns: {set(payload.keys()) - _TOURNAMENT_COLUMNS}"

        if existing is None:
            inserted += 1
            columns = ", ".join(payload)
            placeholders = ", ".join("?" for _ in payload)
            cursor = conn.execute(
                f"INSERT INTO tournaments ({columns}, first_seen_at, last_seen_at) VALUES ({placeholders}, ?, ?)",
                [*payload.values(), now, now],
            )
            conn.execute(
                "INSERT INTO changes(tournament_id, source, source_id, field, old_value, new_value, detected_at) "
                "VALUES (?, ?, ?, 'created', NULL, ?, ?)",
                (cursor.lastrowid, tournament.source, tournament.source_id, tournament.name, now),
            )
        else:
            updated += 1
            set_clause = ", ".join(f"{column} = ?" for column in payload)
            conn.execute(
                f"UPDATE tournaments SET {set_clause}, last_seen_at = ? WHERE id = ?",
                [*payload.values(), now, existing["id"]],
            )
            for field in tracked_fields:
                old_value = existing[field]
                new_value = payload[field]
                if old_value != new_value:
                    if field == "division_details" and not _division_details_has_meaningful_change(old_value, new_value):
                        continue
                    conn.execute(
                        "INSERT INTO changes(tournament_id, source, source_id, field, old_value, new_value, detected_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (existing["id"], tournament.source, tournament.source_id, field, old_value, new_value, now),
                    )

    conn.commit()
    return {"inserted": inserted, "updated": updated, "seen": inserted + updated}


def search_tournaments(
    conn: sqlite3.Connection,
    filters: dict[str, Any],
    team_id: str | None = None,
) -> list[dict[str, Any]]:
    init_db(conn)
    team_id = team_id or get_default_team(conn)["id"]
    settings = get_team_settings(conn, team_id)
    target_age = filters.get("age") or settings["target_age_division"]
    selected_divisions = _normalize_selected_divisions(filters.get("division"))
    threshold = int(filters.get("threshold") or settings["team_count_threshold"])
    radius_miles = int(filters.get("radius_miles") or settings["radius_miles"])

    clauses = []
    params: list[Any] = []
    if source := filters.get("source"):
        clauses.append("t.source = ?")
        params.append(source)
    if start_on_or_after := filters.get("start_on_or_after"):
        clauses.append("(t.start_date IS NULL OR t.start_date >= ?)")
        params.append(start_on_or_after)
    if end_on_or_before := filters.get("end_on_or_before"):
        clauses.append("(t.end_date IS NULL OR t.end_date <= ?)")
        params.append(end_on_or_before)
    if filters.get("single_day"):
        clauses.append("(t.start_date = t.end_date OR t.end_date IS NULL)")
    if search := filters.get("q"):
        clauses.append("(t.name LIKE ? OR t.location LIKE ? OR t.stature LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT t.*, s.status AS shortlist_status, s.priority AS shortlist_priority, s.notes AS shortlist_notes
        FROM tournaments t
        LEFT JOIN shortlist s ON s.tournament_id = t.id AND s.team_id = ?
        {where}
        ORDER BY COALESCE(t.registered_teams, 0) DESC, t.start_date ASC
        """,
        [team_id, *params],
    ).fetchall()
    home_coords = resolve_home_coords(settings.get("home_label", "Huntsville, AL"))
    api_rows = [_row_to_api(row, target_age, threshold, selected_divisions, home_coords=home_coords) for row in rows]
    if age := filters.get("age"):
        api_rows = [row for row in api_rows if _has_exact_age(row["age_divisions"], age)]
    if selected_divisions:
        api_rows = [
            row
            for row in api_rows
            if any(_has_exact_age(row["age_divisions"], division) for division in selected_divisions)
        ]
    api_rows = [
        row
        for row in api_rows
        if row["distance_miles"] is None or row["distance_miles"] <= radius_miles
    ]
    return api_rows


def get_tournament_api(
    conn: sqlite3.Connection,
    tournament_id: int,
    target_age: str,
    threshold: int,
    selected_divisions: list[str] | None = None,
    team_id: str | None = None,
) -> dict[str, Any] | None:
    init_db(conn)
    team_id = team_id or get_default_team(conn)["id"]
    row = conn.execute(
        """
        SELECT t.*, s.status AS shortlist_status, s.priority AS shortlist_priority, s.notes AS shortlist_notes
        FROM tournaments t
        LEFT JOIN shortlist s ON s.tournament_id = t.id AND s.team_id = ?
        WHERE t.id = ?
        """,
        (team_id, tournament_id),
    ).fetchone()
    if row is None:
        return None
    return _row_to_api(row, target_age, threshold, selected_divisions)


def update_tournament_division_teams(
    conn: sqlite3.Connection,
    tournament_id: int,
    division_teams: dict[str, list[dict[str, Any]]],
) -> None:
    init_db(conn)
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE tournaments SET division_teams = ?, last_seen_at = ? WHERE id = ?",
        (json.dumps(division_teams), now, tournament_id),
    )
    conn.commit()


def list_divisions(conn: sqlite3.Connection, age: str | None = None, source: str | None = None) -> list[str]:
    init_db(conn)
    clauses = []
    params: list[Any] = []
    if source:
        clauses.append("source = ?")
        params.append(source)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT age_divisions, division_team_counts, division_details FROM tournaments {where}",
        params,
    ).fetchall()

    values: set[str] = set()
    for row in rows:
        for division in json.loads(row["age_divisions"] or "[]"):
            _add_filter_division(values, str(division), age)
        for division in json.loads(row["division_team_counts"] or "{}"):
            _add_filter_division(values, str(division), age)
        for division in json.loads(row["division_details"] or "{}"):
            _add_filter_division(values, str(division), age)
    return sorted(values, key=_division_sort_key)


def get_changes(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        """
        SELECT c.*, t.name AS tournament_name
        FROM changes c
        LEFT JOIN tournaments t ON t.id = c.tournament_id
        WHERE c.staff_visible = 1
        ORDER BY c.detected_at DESC, c.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def upsert_shortlist(
    conn: sqlite3.Connection,
    tournament_id: int,
    payload: dict[str, Any],
    team_id: str | None = None,
) -> dict[str, Any]:
    init_db(conn)
    team_id = team_id or get_default_team(conn)["id"]
    now = datetime.now(UTC).isoformat()
    status = payload.get("status") or "Watch"
    priority = int(payload.get("priority") or 3)
    notes = payload.get("notes") or ""
    conn.execute(
        """
        INSERT INTO shortlist(team_id, tournament_id, status, priority, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(team_id, tournament_id) DO UPDATE SET
            status = excluded.status,
            priority = excluded.priority,
            notes = excluded.notes,
            updated_at = excluded.updated_at
        """,
        (team_id, tournament_id, status, priority, notes, now, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM shortlist WHERE team_id = ? AND tournament_id = ?",
        (team_id, tournament_id),
    ).fetchone()
    return dict(row)


def record_refresh_start(conn: sqlite3.Connection, source: str) -> int:
    init_db(conn)
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "INSERT INTO refresh_runs(source, started_at, status) VALUES (?, ?, 'running')",
        (source, now),
    )
    conn.commit()
    return int(cursor.lastrowid)


def record_refresh_finish(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    message: str = "",
    tournaments_seen: int = 0,
) -> None:
    conn.execute(
        "UPDATE refresh_runs SET finished_at = ?, status = ?, message = ?, tournaments_seen = ? WHERE id = ?",
        (datetime.now(UTC).isoformat(), status, message, tournaments_seen, run_id),
    )
    conn.commit()


def latest_refresh_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    init_db(conn)
    rows = conn.execute(
        "SELECT * FROM refresh_runs ORDER BY started_at DESC, id DESC LIMIT 20"
    ).fetchall()
    return [dict(row) for row in rows]


def record_stat_refresh_start(conn: sqlite3.Connection, team_id: str, source: str) -> int:
    init_db(conn)
    now = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "INSERT INTO team_stat_refresh(team_id, source, started_at, status) "
        "VALUES (?, ?, ?, 'running')",
        (team_id, source, now),
    )
    conn.commit()
    return int(cursor.lastrowid)


def record_stat_refresh_finish(
    conn: sqlite3.Connection,
    row_id: int,
    status: str,
    teams_refreshed: int = 0,
    message: str = "",
) -> None:
    conn.execute(
        "UPDATE team_stat_refresh "
        "SET finished_at = ?, status = ?, teams_refreshed = ?, message = ? "
        "WHERE id = ?",
        (datetime.now(UTC).isoformat(), status, teams_refreshed, message, row_id),
    )
    conn.commit()


def get_latest_stat_refresh(
    conn: sqlite3.Connection,
    team_id: str,
    source: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM team_stat_refresh
        WHERE team_id = ? AND source = ?
        ORDER BY started_at DESC, id DESC
        LIMIT 1
        """,
        (team_id, source),
    ).fetchone()
    return dict(row) if row else None


def get_hydrated_tournament_teams(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return (source, division_teams_json) for all tournaments with hydrated team data."""
    rows = conn.execute(
        "SELECT source, division_teams FROM tournaments WHERE division_teams != '{}'"
    ).fetchall()
    return [(row["source"], row["division_teams"]) for row in rows]


def _tournament_payload(tournament: Tournament) -> dict[str, Any]:
    return {
        "source": tournament.source,
        "source_id": tournament.source_id,
        "name": tournament.name,
        "detail_url": tournament.detail_url,
        "location": tournament.location,
        "director": tournament.director,
        "start_date": tournament.start_date.isoformat() if tournament.start_date else None,
        "end_date": tournament.end_date.isoformat() if tournament.end_date else None,
        "age_divisions": json.dumps(tournament.age_divisions),
        "registered_teams": tournament.registered_teams,
        "division_team_counts": json.dumps(tournament.division_team_counts),
        "division_confirmed_counts": json.dumps(tournament.division_confirmed_counts),
        "division_details": json.dumps(tournament.division_details),
        "division_teams": json.dumps(tournament.division_teams),
        "team_count_scope": tournament.team_count_scope,
        "stature": tournament.stature,
        "format": tournament.format,
        "tags": json.dumps(tournament.tags),
        "logo_url": tournament.logo_url,
        "distance_miles": tournament.distance_miles
        if tournament.distance_miles is not None
        else estimate_distance_miles(tournament.location),
        "fetched_at": tournament.fetched_at.isoformat(),
    }


def _row_to_api(
    row: sqlite3.Row,
    target_age: str,
    threshold: int,
    selected_divisions: list[str] | None = None,
    home_coords: tuple[float, float] | None = None,
) -> dict[str, Any]:
    data = dict(row)
    age_divisions = json.loads(data["age_divisions"] or "[]")
    division_counts = json.loads(data["division_team_counts"] or "{}")
    division_confirmed_counts = json.loads(data["division_confirmed_counts"] or "{}")
    division_details = json.loads(data["division_details"] or "{}")
    division_teams = json.loads(data.get("division_teams") or "{}")
    tags = json.loads(data["tags"] or "[]")
    selected_divisions = _selected_division_summaries(
        target_age,
        division_counts,
        division_confirmed_counts,
        division_details,
        division_teams,
        selected_divisions,
    )
    target_count = sum(item["registered"] for item in selected_divisions)
    selected_teams = [
        team
        for division in selected_divisions
        for team in division_teams.get(division["division"], [])
    ]
    selected_confirmed_count = sum(item["confirmed"] for item in selected_divisions)
    if selected_divisions and not selected_teams and division_teams.get(target_age):
        selected_teams = division_teams[target_age]
        selected_confirmed_count = sum(1 for team in selected_teams if team.get("confirmed"))
    if not selected_divisions:
        target_count = division_counts.get(target_age, data["registered_teams"])
        selected_teams = division_teams.get(target_age, [])
        if selected_teams:
            target_count = len(selected_teams)
        selected_confirmed_count = (
            sum(1 for team in selected_teams if team.get("confirmed"))
            if selected_teams
            else int(division_confirmed_counts.get(target_age, 0) or 0)
        )
    count_scope = "division" if target_age in division_counts else data["team_count_scope"]
    distance_miles = data["distance_miles"]
    if distance_miles is None:
        distance_miles = estimate_distance_miles(data["location"], home=home_coords or HUNTSVILLE)
    data.update(
        {
            "age_divisions": age_divisions,
            "division_team_counts": division_counts,
            "division_confirmed_counts": division_confirmed_counts,
            "division_details": division_details,
            "division_teams": division_teams,
            "selected_age_divisions": selected_divisions,
            "selected_age_teams": selected_teams,
            "selected_age_confirmed_count": selected_confirmed_count,
            "tags": tags,
            "target_age_division": target_age,
            "target_team_count": target_count,
            "team_count_scope": count_scope,
            "count_warning": count_scope != "division",
            "meets_team_threshold": target_count is not None and target_count >= threshold,
            "distance_miles": distance_miles,
        }
    )
    return data


def _ensure_default_team(conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO teams(id, slug, display_name, active, created_at, updated_at)
        VALUES ('default', 'default', 'Default Staff Team', 1, ?, ?)
        """,
        (now, now),
    )
    existing_settings = {
        row["key"]: json.loads(row["value"])
        for row in conn.execute("SELECT key, value FROM settings")
    }
    seeded_settings = dict(DEFAULT_SETTINGS)
    seeded_settings.update(existing_settings)
    for key, value in seeded_settings.items():
        conn.execute(
            "INSERT OR IGNORE INTO team_settings(team_id, key, value) VALUES ('default', ?, ?)",
            (key, json.dumps(value)),
        )


def _seed_known_team_theme_defaults(conn: sqlite3.Connection) -> None:
    for row in conn.execute("SELECT id, slug FROM teams"):
        defaults = TEAM_THEME_DEFAULTS.get(row["slug"].casefold())
        if not defaults:
            continue
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO team_settings(team_id, key, value) VALUES (?, ?, ?)",
                (row["id"], key, json.dumps(value)),
            )


def _backfill_missing_distances(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, location FROM tournaments WHERE distance_miles IS NULL").fetchall()
    for row in rows:
        distance = estimate_distance_miles(row["location"])
        if distance is None:
            continue
        conn.execute("UPDATE tournaments SET distance_miles = ? WHERE id = ?", (distance, row["id"]))


def _migrate_shortlist_table(conn: sqlite3.Connection) -> None:
    columns = _table_columns(conn, "shortlist")
    if not columns:
        _create_shortlist_table(conn)
        return
    if "team_id" in columns:
        return

    conn.execute("ALTER TABLE shortlist RENAME TO shortlist_legacy")
    _create_shortlist_table(conn)
    conn.execute(
        """
        INSERT INTO shortlist(id, team_id, tournament_id, status, priority, notes, created_at, updated_at)
        SELECT id, 'default', tournament_id, status, priority, notes, created_at, updated_at
        FROM shortlist_legacy
        """
    )
    conn.execute("DROP TABLE shortlist_legacy")


def _create_shortlist_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shortlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT NOT NULL,
            tournament_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Watch',
            priority INTEGER NOT NULL DEFAULT 3,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(team_id, tournament_id),
            FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
        )
        """
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table!r}")
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 100_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, expected = stored.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 100_000)
    return hmac.compare_digest(digest.hex(), expected)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ensure_ncs_team_records_table(conn: sqlite3.Connection) -> None:
    """Create ncs_team_records table if it doesn't exist (idempotent)."""
    from baseball_aggregator.scrapers.ncs_teams import init_ncs_team_records_table
    init_ncs_team_records_table(conn)


_LEGACY_DEFAULT_SOURCES = {"ncs", "usssa", "perfect_game"}


def _backfill_enabled_sources(conn: sqlite3.Connection) -> None:
    """Append newly-supported sources to settings that were using the old defaults.

    Only updates rows whose enabled_sources is a superset of the previous
    defaults (ncs/usssa/perfect_game), which indicates they were the old
    default rather than a deliberately-restricted subset.
    """
    new_sources: list[str] = [
        s for s in DEFAULT_SETTINGS["enabled_sources"] if s not in _LEGACY_DEFAULT_SOURCES
    ]
    if not new_sources:
        return

    def _maybe_merge(current: list[str]) -> list[str] | None:
        if not _LEGACY_DEFAULT_SOURCES.issubset(current):
            return None
        merged = current + [s for s in new_sources if s not in current]
        return merged if merged != current else None

    # Global settings table
    row = conn.execute("SELECT value FROM settings WHERE key = 'enabled_sources'").fetchone()
    if row:
        merged = _maybe_merge(json.loads(row["value"]))
        if merged is not None:
            conn.execute(
                "UPDATE settings SET value = ? WHERE key = 'enabled_sources'",
                (json.dumps(merged),),
            )

    # Per-team settings table
    for ts_row in conn.execute(
        "SELECT team_id, value FROM team_settings WHERE key = 'enabled_sources'"
    ).fetchall():
        merged = _maybe_merge(json.loads(ts_row["value"]))
        if merged is not None:
            conn.execute(
                "UPDATE team_settings SET value = ? WHERE team_id = ? AND key = 'enabled_sources'",
                (json.dumps(merged), ts_row["team_id"]),
            )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table!r}")
    if not _ALLOWED_COLUMN_PATTERN.match(column):
        raise ValueError(f"Invalid column name: {column!r}")
    columns = _table_columns(conn, table)
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _has_exact_age(age_divisions: list[str], selected_age: str) -> bool:
    selected = selected_age.upper()
    for division in age_divisions:
        value = str(division).upper()
        if value == selected:
            return True
        if value.startswith(f"{selected} "):
            return True
    return False


def _add_filter_division(values: set[str], division: str, selected_age: str | None = None) -> None:
    value = division.strip()
    if not value:
        return
    age_match = re.match(r"^(\d{1,2}U)\b", value, re.IGNORECASE)
    if not age_match:
        return
    age = age_match.group(1).upper()
    if selected_age and not value.upper().startswith(f"{selected_age.upper()} "):
        return
    if value.upper() == age:
        return
    values.add(value)


def _normalize_selected_divisions(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw_values = [value]
    else:
        raw_values = list(value)
    divisions = []
    for raw in raw_values:
        for item in str(raw).split(","):
            item = item.strip()
            if item and item not in divisions:
                divisions.append(item)
    return divisions


def _division_sort_key(value: str) -> tuple[int, str]:
    match = re.match(r"^(\d{1,2})U\b(.*)$", value, re.IGNORECASE)
    if not match:
        return (99, value)
    return (int(match.group(1)), match.group(2).strip())


def _selected_division_summaries(
    selected_age: str,
    division_counts: dict[str, int],
    division_confirmed_counts: dict[str, int],
    division_details: dict[str, dict[str, Any]],
    division_teams: dict[str, list[dict[str, Any]]],
    selected_divisions: list[str] | None = None,
) -> list[dict[str, Any]]:
    selected = selected_age.upper()
    selected_division_values = {division.upper() for division in selected_divisions or []}
    summaries = []
    for division in sorted(division_counts):
        value = division.upper()
        if value == selected:
            continue
        if not value.startswith(f"{selected} "):
            continue
        if selected_division_values and value not in selected_division_values:
            continue

        teams = division_teams.get(division, [])
        registered = len(teams) if teams else int(division_counts[division] or 0)
        confirmed = (
            sum(1 for team in teams if team.get("confirmed"))
            if teams
            else int(division_confirmed_counts.get(division, 0) or 0)
        )
        summaries.append(
            {
                "division": division,
                "registered": registered,
                "confirmed": confirmed,
                "details": division_details.get(division, {}),
            }
        )
    return summaries


# ── team_records ──────────────────────────────────────────────────────────────────────────────

def upsert_team_records(
    conn: sqlite3.Connection,
    team_id: str,
    records: list[dict],
) -> int:
    """Insert or replace team W-L-T records. Returns count of rows written.

    Each record dict must have: source, team_name, age_division, season,
    wins, losses, ties. detail_url and scraped_at are optional.
    """
    now = datetime.now(UTC).isoformat()
    written = 0
    for r in records:
        conn.execute(
            """
            INSERT INTO team_records
                (team_id, source, team_name, age_division, season,
                 wins, losses, ties, detail_url, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, source, team_name, season) DO UPDATE SET
                age_division = excluded.age_division,
                wins         = excluded.wins,
                losses       = excluded.losses,
                ties         = excluded.ties,
                detail_url   = excluded.detail_url,
                scraped_at   = excluded.scraped_at
            """,
            (
                team_id,
                r["source"],
                r["team_name"],
                r.get("age_division") or "",
                r["season"],
                int(r.get("wins") or 0),
                int(r.get("losses") or 0),
                int(r.get("ties") or 0),
                r.get("detail_url") or "",
                r.get("scraped_at") or now,
            ),
        )
        written += 1
    conn.commit()
    return written


def get_team_records(
    conn: sqlite3.Connection,
    team_id: str,
    age_division: str | None = None,
    season: str | None = None,
) -> list[dict]:
    """Return team_records rows, optionally filtered by age_division and/or season."""
    query = "SELECT * FROM team_records WHERE team_id = ?"
    params: list = [team_id]
    if age_division:
        query += " AND age_division = ?"
        params.append(age_division)
    if season:
        query += " AND season = ?"
        params.append(season)
    query += " ORDER BY source, team_name"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_available_seasons(conn: sqlite3.Connection, team_id: str) -> list[str]:
    """Return distinct season values present in team_records, sorted descending."""
    rows = conn.execute(
        "SELECT DISTINCT season FROM team_records WHERE team_id = ? ORDER BY season DESC",
        (team_id,),
    ).fetchall()
    return [r["season"] for r in rows]
