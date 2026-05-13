"""Tests for the per-team stats refresh service + endpoint.

Covers:
- The state extraction from shortlisted teams' city_state (with home_label fallback)
- USSSA URL collection scoped to shortlisted teams
- Perfect Game reports unsupported
- team_stat_refresh rows written
- /api/team-analysis sources_status / sources_last_refreshed enrichment
- Skip-on-lock behavior of refresh_team_stats
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import sqlite3
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from baseball_aggregator import services, stats
from baseball_aggregator.models import Tournament
from baseball_aggregator.storage import (
    connect,
    get_latest_stat_refresh,
    init_db,
    upsert_shortlist,
    upsert_team_records,
    upsert_tournaments,
)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point the storage layer at a temp SQLite file so services using connect()
    operate on an isolated DB per test."""
    monkeypatch.setenv("STAFF_TOOL_DATA_DIR", str(tmp_path))
    with connect() as conn:
        init_db(conn)
    return tmp_path


def _seed_shortlisted_usssa_tournament(team_id: str = "default") -> int:
    with connect() as conn:
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="usssa",
                    source_id="usssa-1",
                    name="USSSA Spring Classic",
                    detail_url="https://usssa.example/event/1",
                    location="Madison, AL",
                    age_divisions=["8U"],
                    registered_teams=2,
                    division_team_counts={"8U OPEN": 2},
                    division_teams={
                        "8U OPEN": [
                            {
                                "team_name": "Madison Mavericks",
                                "city_state": "Madison, AL",
                                "record": "5-2-0",
                                "detail_url": "https://usssa.example/teamHome?teamID=111",
                            },
                            {
                                "team_name": "Cullman Crushers",
                                "city_state": "Cullman, AL",
                                "record": "3-1-0",
                                "detail_url": "https://usssa.example/teamHome?teamID=222",
                            },
                        ],
                    },
                    team_count_scope="division",
                )
            ],
        )
        row = conn.execute("SELECT id FROM tournaments WHERE source = 'usssa'").fetchone()
        upsert_shortlist(conn, row["id"], {"status": "Interested"}, team_id=team_id)
        return int(row["id"])


def _run(coro):
    """Run a coroutine safely from a sync test.

    _run() raises RuntimeError if another event loop (e.g. from
    pytest-playwright) is already running on this thread.  Delegating to a
    fresh worker thread avoids that constraint entirely.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ── Unit-ish tests (no DB) ─────────────────────────────────────────────────

def test_extract_state_uses_city_state_then_fallback():
    assert services._extract_state("Madison, AL", None) == "AL"
    assert services._extract_state("Cullman, AL", "Atlanta, GA") == "AL"
    assert services._extract_state(None, "Atlanta, GA") == "GA"
    assert services._extract_state(" ", "Charlotte, NC") == "NC"
    assert services._extract_state("no comma here", "no fallback") is None


# ── DB-backed tests (use isolated_db fixture) ──────────────────────────────

def test_collect_shortlist_states_falls_back_to_home_label(isolated_db):
    with connect() as conn:
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="ncs-1",
                    name="Mystery Tournament",
                    detail_url="https://ncs.example/event/1",
                    location="Unknown",
                    age_divisions=["8U"],
                    division_team_counts={"8U OPEN": 1},
                    division_teams={
                        "8U OPEN": [
                            {"team_name": "Ghost Team", "record": "1-0-0"},
                        ],
                    },
                )
            ],
        )
        row = conn.execute("SELECT id FROM tournaments").fetchone()
        upsert_shortlist(conn, row["id"], {"status": "Interested"}, team_id="default")
        states = services._collect_shortlist_states(conn, "default", "8U", "Huntsville, AL")
    assert states == {"AL"}


def test_collect_shortlist_states_skips_other_age_divisions(isolated_db):
    with connect() as conn:
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="ncs-2",
                    name="Mixed Age Tournament",
                    detail_url="https://ncs.example/event/2",
                    age_divisions=["8U", "10U"],
                    division_team_counts={"8U OPEN": 1, "10U OPEN": 1},
                    division_teams={
                        "8U OPEN": [{"team_name": "Eights", "city_state": "Madison, AL"}],
                        "10U OPEN": [{"team_name": "Tens", "city_state": "Atlanta, GA"}],
                    },
                )
            ],
        )
        row = conn.execute("SELECT id FROM tournaments").fetchone()
        upsert_shortlist(conn, row["id"], {"status": "Registered"}, team_id="default")
        states = services._collect_shortlist_states(conn, "default", "8U", "")
    assert states == {"AL"}
    assert "GA" not in states


def test_shortlisted_team_data_returns_usssa_only_and_keys(isolated_db):
    _seed_shortlisted_usssa_tournament()
    with connect() as conn:
        usssa_dicts, keys = services._shortlisted_team_data(conn, "default", "8U")
    assert len(usssa_dicts) == 1
    assert "madison mavericks" in keys
    assert "cullman crushers" in keys


def test_refresh_team_stats_marks_pg_unsupported_and_skips_disabled_sources(isolated_db):
    _seed_shortlisted_usssa_tournament()

    async def _fake_fetch(urls):
        return [
            {
                "source": "usssa",
                "team_name": "Madison Mavericks",
                "age_division": "8U",
                "season": stats.current_season_year(),
                "wins": 6,
                "losses": 1,
                "ties": 0,
                "detail_url": urls[0],
            }
        ]

    with patch(
        "baseball_aggregator.collectors.usssa.fetch_usssa_team_histories",
        side_effect=_fake_fetch,
    ):
        result = _run(
            services.refresh_team_stats("default", enabled_sources=["usssa"])
        )

    assert result["skipped"] is False
    assert result["stats"]["ncs"]["status"] == "skipped"
    assert result["stats"]["perfect_game"]["status"] == "unsupported"
    assert result["stats"]["usssa"]["status"] == "success"
    assert result["stats"]["usssa"]["records_written"] == 1


def test_refresh_team_stats_filters_usssa_records_to_shortlist(isolated_db):
    _seed_shortlisted_usssa_tournament()

    async def _fake_fetch(urls):
        return [
            {
                "source": "usssa",
                "team_name": "Madison Mavericks",
                "age_division": "8U",
                "season": stats.current_season_year(),
                "wins": 6, "losses": 1, "ties": 0,
                "detail_url": "https://usssa.example/teamHome?teamID=111",
            },
            {
                "source": "usssa",
                "team_name": "Random Other Team",
                "age_division": "8U",
                "season": stats.current_season_year(),
                "wins": 99, "losses": 0, "ties": 0,
                "detail_url": "https://usssa.example/teamHome?teamID=999",
            },
        ]

    with patch(
        "baseball_aggregator.collectors.usssa.fetch_usssa_team_histories",
        side_effect=_fake_fetch,
    ):
        result = _run(
            services.refresh_team_stats("default", enabled_sources=["usssa"])
        )
    assert result["stats"]["usssa"]["records_written"] == 1


def test_refresh_team_stats_records_stat_refresh_row(isolated_db):
    _seed_shortlisted_usssa_tournament()

    async def _fake_fetch(_):
        return []

    with patch(
        "baseball_aggregator.collectors.usssa.fetch_usssa_team_histories",
        side_effect=_fake_fetch,
    ):
        _run(services.refresh_team_stats("default", enabled_sources=["usssa"]))

    with connect() as conn:
        latest = get_latest_stat_refresh(conn, "default", "usssa")
    assert latest is not None
    assert latest["status"] == "success"
    assert latest["finished_at"]


def test_refresh_team_stats_skip_when_lock_held(isolated_db):
    services._stats_refresh_lock.acquire()
    try:
        result = _run(
            services.refresh_team_stats("default", enabled_sources=["usssa"])
        )
    finally:
        services._stats_refresh_lock.release()
    assert result == {"skipped": True, "message": "Stats refresh already running."}


def test_team_analysis_records_emits_sources_status(isolated_db):
    _seed_shortlisted_usssa_tournament()
    season = stats.current_season_year()

    fresh_iso = datetime.now(UTC).isoformat()
    stale_iso = (datetime.now(UTC) - timedelta(days=stats.STATS_STALE_DAYS + 5)).isoformat()
    with connect() as conn:
        upsert_team_records(
            conn,
            "default",
            [
                {
                    "source": "usssa",
                    "team_name": "Madison Mavericks",
                    "age_division": "8U",
                    "season": season,
                    "wins": 6, "losses": 1, "ties": 0,
                    "detail_url": "",
                    "scraped_at": fresh_iso,
                },
                {
                    "source": "ncs",
                    "team_name": "Cullman Crushers",
                    "age_division": "8U",
                    "season": season,
                    "wins": 4, "losses": 2, "ties": 1,
                    "detail_url": "",
                    "scraped_at": stale_iso,
                },
            ],
        )
        result = stats.team_analysis_records(conn, "8U", team_id="default", season=season)

    by_name = {t["team_name"]: t for t in result["teams"]}
    mav = by_name["Madison Mavericks"]
    assert mav["sources_status"]["usssa"] == "loaded"
    assert mav["sources_status"]["ncs"] == "missing"
    assert mav["sources_status"]["perfect_game"] == "unsupported"

    crush = by_name["Cullman Crushers"]
    assert crush["sources_status"]["ncs"] == "stale"

    assert "sources_last_refreshed" in result
    assert set(result["sources_last_refreshed"].keys()) == {"ncs", "usssa", "perfect_game"}
    assert result["stale_threshold_days"] == stats.STATS_STALE_DAYS
