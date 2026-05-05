from __future__ import annotations

import threading

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
    update_tournament_division_teams,
    upsert_tournaments,
)

_refresh_lock = threading.Lock()


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
