"""Stats enrichment worker.

Scrapes USSSA team home pages and writes W-L-T records into the team_records
table. Runs per app-team so each tenant's data stays isolated.

Usage:
    python -m scripts.stats_worker                     # all teams
    python -m scripts.stats_worker --team-id <id>      # one team
    python -m scripts.stats_worker --team-slug <slug>  # one team by slug

Set STATS_ENRICHMENT=true in env to enable this automatically at the end
of each background refresh cycle (called via await enrich_team_records()).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow running as a script from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from baseball_aggregator.collectors.usssa import (
    extract_usssa_team_ids_from_tournaments,
    fetch_usssa_team_histories,
)
from baseball_aggregator.stats import current_season_year
from baseball_aggregator.storage import connect, get_available_seasons, upsert_team_records


def _get_all_tournaments_for_team(conn, team_id: str) -> list[dict]:
    """Return all tournaments rows (with division_teams JSON) for a given team."""
    rows = conn.execute(
        """
        SELECT t.division_teams
        FROM tournaments t
        JOIN shortlist s ON s.tournament_id = t.id
        WHERE s.team_id = ?
        """,
        (team_id,),
    ).fetchall()
    return [dict(r) for r in rows]


async def enrich_team_records(team_id: str) -> dict:
    """Async enrichment pass for one app team. Returns counts dict."""
    with connect() as conn:
        tournaments = _get_all_tournaments_for_team(conn, team_id)

    if not tournaments:
        return {"usssa": 0, "team_id": team_id}

    # Extract deduplicated USSSA team home URLs
    team_id_to_url = extract_usssa_team_ids_from_tournaments(tournaments)
    urls = list(team_id_to_url.values())

    print(f"[stats_worker] team={team_id}: fetching {len(urls)} USSSA team home pages…")
    records = await fetch_usssa_team_histories(urls)
    print(f"[stats_worker] team={team_id}: parsed {len(records)} season records")

    if records:
        with connect() as conn:
            written = upsert_team_records(conn, team_id, records)
        print(f"[stats_worker] team={team_id}: upserted {written} rows into team_records")
    else:
        written = 0

    return {"usssa": written, "team_id": team_id}


def _list_teams(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, slug FROM teams WHERE active = 1 AND id != 'default'"
    ).fetchall()
    return [dict(r) for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich team_records from USSSA team pages")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--team-id", help="Enrich a specific team by internal ID")
    group.add_argument("--team-slug", help="Enrich a specific team by slug")
    args = parser.parse_args()

    with connect() as conn:
        if args.team_id:
            teams = [{"id": args.team_id, "slug": args.team_id}]
        elif args.team_slug:
            row = conn.execute(
                "SELECT id, slug FROM teams WHERE slug = ?", (args.team_slug,)
            ).fetchone()
            if not row:
                print(f"[stats_worker] No team found with slug '{args.team_slug}'")
                sys.exit(1)
            teams = [dict(row)]
        else:
            teams = _list_teams(conn)

    print(f"[stats_worker] Processing {len(teams)} team(s)…")
    total_usssa = 0
    for team in teams:
        result = asyncio.run(enrich_team_records(team["id"]))
        total_usssa += result.get("usssa", 0)
        # Show available seasons after enrichment
        with connect() as conn:
            seasons = get_available_seasons(conn, team["id"])
        print(f"[stats_worker] team={team['slug']}: seasons in DB: {seasons or ['(none yet)']}")

    print(f"[stats_worker] Done. Total USSSA records written: {total_usssa}")


if __name__ == "__main__":
    main()
