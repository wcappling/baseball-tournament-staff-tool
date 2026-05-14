from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from typing import Any

import httpx

from baseball_aggregator.collectors import perfect_game, usssa
from baseball_aggregator.collectors.registry import get_collector, list_collectors
from baseball_aggregator.storage import (
    connect,
    get_tournament_api,
    get_settings,
    get_team_settings,
    record_refresh_finish,
    record_refresh_start,
    record_stat_refresh_finish,
    record_stat_refresh_start,
    update_tournament_division_teams,
    upsert_team_records,
    upsert_tournaments,
)

log = logging.getLogger(__name__)

_refresh_lock = threading.Lock()
_stats_refresh_lock = threading.Lock()

_STATE_RE = re.compile(r"\b([A-Z]{2})\s*$")


def refresh_sources(sources: list[str] | None = None) -> dict:
    if not _refresh_lock.acquire(blocking=False):
        return {"status": "skipped", "message": "Refresh already running"}
    try:
        with connect() as conn:
            settings = get_settings(conn)
            selected = sources or settings["enabled_sources"]
            summary = {}
            for source in selected:
                if source not in list_collectors():
                    summary[source] = {"status": "skipped", "message": "Unknown source"}
                    continue

                run_id = record_refresh_start(conn, source)
                try:
                    collector = get_collector(source)
                    tournaments = collector.fetch_tournaments(
                        radius_miles=settings["radius_miles"],
                        target_age=settings["target_age_division"],
                    )
                    counts = upsert_tournaments(conn, tournaments)
                    message = "OK" if tournaments else "No live collector results yet"
                    record_refresh_finish(conn, run_id, "success", message, len(tournaments))
                    summary[source] = {"status": "success", **counts, "message": message}
                except Exception as exc:
                    record_refresh_finish(conn, run_id, "error", str(exc), 0)
                    summary[source] = {"status": "error", "message": str(exc)}
            return summary
    finally:
        _refresh_lock.release()


def hydrate_tournament_teams(
    tournament_id: int,
    target_age: str,
    selected_divisions: list[str] | None = None,
    team_id: str | None = None,
) -> dict | None:
    with connect() as conn:
        settings = get_team_settings(conn, team_id) if team_id else get_settings(conn)
        threshold = int(settings["team_count_threshold"])
        row = get_tournament_api(conn, tournament_id, target_age, threshold, selected_divisions, team_id=team_id)
        if row is None:
            return None
        if row["source"] not in {usssa.SOURCE, perfect_game.SOURCE}:
            return row

        division_teams = dict(row["division_teams"])
        division_details = row["division_details"]
        divisions_to_fetch = [
            item["division"]
            for item in row["selected_age_divisions"]
            if row["division_team_counts"].get(item["division"], 0) > 0
            and not division_teams.get(item["division"])
        ]
        if not divisions_to_fetch:
            return row

        headers = usssa.HEADERS if row["source"] == usssa.SOURCE else perfect_game.HEADERS
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            for division in divisions_to_fetch:
                try:
                    teams = fetch_division_teams(row["source"], client, division_details.get(division, {}), division)
                except (httpx.HTTPError, RuntimeError, ValueError):
                    teams = []
                division_teams[division] = teams

        age_key = target_age.upper()
        division_teams[age_key] = [
            team
            for division, teams in division_teams.items()
            if division.upper().startswith(f"{age_key} ") and division.upper() != age_key
            for team in teams
        ]
        update_tournament_division_teams(conn, tournament_id, division_teams)
        return get_tournament_api(conn, tournament_id, target_age, threshold, selected_divisions, team_id=team_id)


def get_tournament_detail(
    tournament_id: int,
    target_age: str,
    threshold: int,
    selected_divisions: list[str] | None = None,
    team_id: str | None = None,
) -> dict | None:
    with connect() as conn:
        return get_tournament_api(conn, tournament_id, target_age, threshold, selected_divisions, team_id=team_id)


def _extract_state(city_state: str | None, fallback: str | None) -> str | None:
    if city_state:
        m = _STATE_RE.search(city_state.upper())
        if m:
            return m.group(1)
    if fallback:
        m = _STATE_RE.search(fallback.upper())
        if m:
            return m.group(1)
    return None


def _shortlisted_team_data(
    conn: sqlite3.Connection,
    team_id: str,
    age_division: str,
) -> tuple[list[dict], set[str]]:
    """Return (USSSA-tournament-rows, shortlisted-team-name-keys) for shortlisted entries.

    age_division is uppercased prefix (e.g. "8U"). Team name keys are
    lowercased and stripped, matching the keying used in stats.py.
    """
    rows = conn.execute(
        """
        SELECT t.id, t.source, t.division_teams
        FROM tournaments t
        JOIN shortlist s ON s.tournament_id = t.id
        WHERE s.team_id = ? AND s.status IN ('Interested', 'Registered')
        """,
        (team_id,),
    ).fetchall()

    age_prefix = age_division.strip().upper()
    usssa_tournament_dicts: list[dict] = []
    shortlist_team_keys: set[str] = set()

    for row in rows:
        try:
            division_teams: dict[str, list[dict]] = json.loads(row["division_teams"] or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if row["source"] == usssa.SOURCE:
            filtered_divisions = {
                div: teams
                for div, teams in division_teams.items()
                if div.upper().startswith(age_prefix)
            }
            usssa_tournament_dicts.append({"division_teams": filtered_divisions})
        for division, teams in division_teams.items():
            if not division.upper().startswith(age_prefix):
                continue
            if not isinstance(teams, list):
                continue
            for team in teams:
                name = (team.get("team_name") or "").strip()
                if name:
                    shortlist_team_keys.add(name.lower())

    return usssa_tournament_dicts, shortlist_team_keys


def _collect_shortlist_states(
    conn: sqlite3.Connection,
    team_id: str,
    age_division: str,
    home_label_fallback: str | None,
) -> set[str]:
    """Return the set of two-letter state codes covering shortlisted teams.

    Parses ``city_state`` from division_teams entries; falls back to the
    calling team's ``home_label`` state if no city_state is present.
    """
    rows = conn.execute(
        """
        SELECT t.division_teams
        FROM tournaments t
        JOIN shortlist s ON s.tournament_id = t.id
        WHERE s.team_id = ? AND s.status IN ('Interested', 'Registered')
        """,
        (team_id,),
    ).fetchall()

    age_prefix = age_division.strip().upper()
    states: set[str] = set()

    for row in rows:
        try:
            division_teams: dict[str, list[dict]] = json.loads(row["division_teams"] or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        for division, teams in division_teams.items():
            if not division.upper().startswith(age_prefix):
                continue
            if not isinstance(teams, list):
                continue
            for team in teams:
                state = _extract_state(team.get("city_state"), None)
                if state:
                    states.add(state)

    if not states and home_label_fallback:
        fallback_state = _extract_state(None, home_label_fallback)
        if fallback_state:
            states.add(fallback_state)
    return states


async def _refresh_ncs_stats(
    team_id: str,
    age_division: str,
    states: set[str],
) -> dict[str, Any]:
    from fastapi.concurrency import run_in_threadpool

    from baseball_aggregator.scrapers import ncs_teams as ncs_teams_scraper

    if not states:
        return {
            "status": "success",
            "teams_refreshed": 0,
            "states_scraped": [],
            "message": "No states identified from shortlist or home_label.",
        }

    total_upserted = 0
    states_scraped: list[str] = []
    errors: list[str] = []

    for state in sorted(states):
        def _do_scrape(state: str = state) -> dict[str, Any]:
            with connect() as conn:
                return ncs_teams_scraper.scrape_ncs_teams(
                    conn,
                    state=state,
                    age_division=age_division,
                    season_id=ncs_teams_scraper.DEFAULT_SEASON_ID,
                    team_id=team_id,
                )

        try:
            result = await run_in_threadpool(_do_scrape)
            total_upserted += int(result.get("teams_upserted") or 0)
            states_scraped.append(state)
        except Exception as exc:
            log.warning("NCS stats refresh failed for state=%s: %s", state, exc)
            errors.append(f"{state}: {exc}")

    status = "success" if not errors else ("partial" if states_scraped else "error")
    return {
        "status": status,
        "teams_refreshed": total_upserted,
        "states_scraped": states_scraped,
        "errors": errors,
    }


async def _refresh_usssa_stats(
    team_id: str,
    usssa_tournament_dicts: list[dict],
    shortlist_team_keys: set[str],
) -> dict[str, Any]:
    from baseball_aggregator.collectors.usssa import (
        extract_usssa_team_ids_from_tournaments,
        fetch_usssa_team_histories,
    )

    if not usssa_tournament_dicts:
        return {
            "status": "success",
            "urls_fetched": 0,
            "records_written": 0,
            "message": "No USSSA tournaments in shortlist.",
        }

    team_id_to_url = extract_usssa_team_ids_from_tournaments(usssa_tournament_dicts)
    urls = list(team_id_to_url.values())
    if not urls:
        return {
            "status": "success",
            "urls_fetched": 0,
            "records_written": 0,
            "message": "No USSSA team detail URLs in shortlist.",
        }

    try:
        records = await fetch_usssa_team_histories(urls)
    except Exception as exc:
        log.warning("USSSA team history fetch failed: %s", exc)
        return {"status": "error", "urls_fetched": len(urls), "records_written": 0, "message": str(exc)}

    if shortlist_team_keys:
        records = [
            r for r in records
            if (r.get("team_name") or "").strip().lower() in shortlist_team_keys
        ]

    written = 0
    if records:
        with connect() as conn:
            written = upsert_team_records(conn, team_id, records)

    return {
        "status": "success",
        "urls_fetched": len(urls),
        "records_written": written,
    }


async def refresh_team_stats(
    team_id: str,
    enabled_sources: list[str] | None = None,
) -> dict[str, Any]:
    """Hydrate ``team_records`` for the caller's Interested/Registered shortlist.

    Does NOT re-pull tournament listings. Returns per-source status.
    Acquires a non-blocking stats-refresh lock; returns ``{"skipped": True}``
    if another stats refresh is already in flight for this process.
    """
    if not _stats_refresh_lock.acquire(blocking=False):
        return {"skipped": True, "message": "Stats refresh already running."}
    try:
        with connect() as conn:
            settings = get_team_settings(conn, team_id)
            age_division = (settings.get("target_age_division") or "8U").strip().upper()
            home_label = settings.get("home_label") or ""
            sources = enabled_sources or settings.get("enabled_sources") or []
            usssa_tournament_dicts, shortlist_team_keys = _shortlisted_team_data(
                conn, team_id, age_division
            )
            states = _collect_shortlist_states(conn, team_id, age_division, home_label)

        result: dict[str, Any] = {"skipped": False, "stats": {}}

        if "ncs" in sources:
            with connect() as conn:
                run_id = record_stat_refresh_start(conn, team_id, "ncs")
            ncs_result = await _refresh_ncs_stats(team_id, age_division, states)
            with connect() as conn:
                record_stat_refresh_finish(
                    conn,
                    run_id,
                    ncs_result["status"],
                    teams_refreshed=int(ncs_result.get("teams_refreshed") or 0),
                    message="; ".join(ncs_result.get("errors", [])) or ncs_result.get("message", ""),
                )
            result["stats"]["ncs"] = ncs_result
        else:
            result["stats"]["ncs"] = {"status": "skipped", "message": "Source not enabled."}

        if "usssa" in sources:
            with connect() as conn:
                run_id = record_stat_refresh_start(conn, team_id, "usssa")
            usssa_result = await _refresh_usssa_stats(
                team_id, usssa_tournament_dicts, shortlist_team_keys
            )
            with connect() as conn:
                record_stat_refresh_finish(
                    conn,
                    run_id,
                    usssa_result["status"],
                    teams_refreshed=int(usssa_result.get("records_written") or 0),
                    message=usssa_result.get("message", ""),
                )
            result["stats"]["usssa"] = usssa_result
        else:
            result["stats"]["usssa"] = {"status": "skipped", "message": "Source not enabled."}

        result["stats"]["perfect_game"] = {
            "status": "unsupported",
            "message": "Per-team Perfect Game hydration not implemented.",
        }
        return result
    finally:
        _stats_refresh_lock.release()


def fetch_division_teams(
    source: str,
    client: httpx.Client,
    details: dict,
    division: str,
) -> list[dict]:
    if source == usssa.SOURCE:
        division_id = details.get("division_id")
        if not division_id:
            return []
        return usssa.fetch_seeding_report_teams(client, str(division_id), division)
    if source == perfect_game.SOURCE:
        event_id = details.get("event_id")
        if not event_id:
            return []
        return perfect_game.fetch_tournament_teams(client, str(event_id), division)
    return []
