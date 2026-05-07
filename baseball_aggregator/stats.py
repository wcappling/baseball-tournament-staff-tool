from __future__ import annotations

import json
import re
import sqlite3
from typing import Any


def parse_record(s: str | None) -> tuple[int, int, int] | None:
    """Parse W-L, W-L-T, or 'W-L in YEAR' into (wins, losses, ties).

    Returns None if the string is empty or doesn't look like a record.
    """
    if not s:
        return None
    # Strip " in YYYY" suffix (Perfect Game format)
    cleaned = re.sub(r"\s+in\s+\d{4}\s*$", "", s.strip(), flags=re.IGNORECASE)
    match = re.match(r"^(\d+)-(\d+)(?:-(\d+))?$", cleaned.strip())
    if not match:
        return None
    wins = int(match.group(1))
    losses = int(match.group(2))
    ties = int(match.group(3)) if match.group(3) is not None else 0
    return (wins, losses, ties)


def _is_aggregate_key(division: str) -> bool:
    """Return True for bare age-only keys like '8U', '10U' that aggregate sub-divisions."""
    return bool(re.match(r"^\d{1,2}U$", division.strip(), re.IGNORECASE))


def _format_record(wins: int, losses: int, ties: int) -> str:
    if ties:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def aggregate_team_records(conn: sqlite3.Connection, age_division: str) -> list[dict[str, Any]]:
    """Aggregate W-L-T records for all teams from hydrated tournament data.

    Also merges records scraped directly from the NCS Teams listing page
    (stored in ``ncs_team_records``) so that teams whose records exist on NCS
    but whose tournament entries haven't been hydrated yet are still visible.

    Groups teams by normalized name, accumulates wins/losses/ties per source,
    and returns a list sorted by win% descending (then total games descending).
    """
    rows = conn.execute(
        "SELECT source, division_teams FROM tournaments WHERE division_teams != '{}'",
    ).fetchall()

    age_prefix = age_division.strip().upper()

    # Keyed by normalized team name
    team_map: dict[str, dict[str, Any]] = {}

    for row in rows:
        source = row["source"]
        try:
            division_teams: dict[str, list[dict[str, Any]]] = json.loads(row["division_teams"])
        except (json.JSONDecodeError, TypeError):
            continue

        for division, teams in division_teams.items():
            if _is_aggregate_key(division):
                continue
            if not division.upper().startswith(age_prefix):
                continue
            if not isinstance(teams, list):
                continue

            for team in teams:
                raw_name: str = team.get("team_name") or ""
                if not raw_name.strip():
                    continue

                key = raw_name.strip().lower()
                if key not in team_map:
                    team_map[key] = {
                        "team_name": raw_name.strip(),
                        "city_state": team.get("city_state") or "",
                        "sources": {},
                    }

                record_str = team.get("record") or ""
                parsed = parse_record(record_str)
                if parsed is None:
                    continue

                wins, losses, ties = parsed
                src = team_map[key]["sources"].setdefault(
                    source, {"wins": 0, "losses": 0, "ties": 0}
                )
                src["wins"] += wins
                src["losses"] += losses
                src["ties"] += ties

    results: list[dict[str, Any]] = []
    for data in team_map.values():
        sources = data["sources"]
        total_wins = sum(s["wins"] for s in sources.values())
        total_losses = sum(s["losses"] for s in sources.values())
        total_ties = sum(s["ties"] for s in sources.values())
        total_games = total_wins + total_losses + total_ties
        win_pct = total_wins / total_games if total_games > 0 else 0.0

        def src_record(source_key: str) -> str:
            s = sources.get(source_key)
            if not s:
                return ""
            return _format_record(s["wins"], s["losses"], s["ties"])

        results.append({
            "team_name": data["team_name"],
            "city_state": data["city_state"],
            "ncs_record": src_record("ncs"),
            "usssa_record": src_record("usssa"),
            "perfect_game_record": src_record("perfect_game"),
            "cumulative_record": _format_record(total_wins, total_losses, total_ties),
            "win_pct": round(win_pct, 4),
            "total_games": total_games,
            "sources_seen": list(sources.keys()),
        })

    results.sort(key=lambda x: (-x["win_pct"], -x["total_games"]))
    return results


def team_analysis_records(
    conn: sqlite3.Connection,
    age_division: str,
    team_id: str = "",
) -> dict[str, Any]:
    """Aggregate team records from tournaments marked Interested or Registered.

    Returns a dict with per-team breakdown including which tournaments each
    team appears in and their W-L-T records from each source.
    """
    rows = conn.execute(
        """
        SELECT t.id, t.name, t.source, t.start_date, t.end_date,
               t.detail_url, t.division_teams, s.status
        FROM tournaments t
        JOIN shortlist s ON t.id = s.tournament_id
        WHERE s.team_id = ? AND s.status IN ('Interested', 'Registered')
        ORDER BY t.start_date ASC
        """,
        (team_id,),
    ).fetchall()

    age_prefix = age_division.strip().upper()

    tournament_info: dict[int, dict[str, Any]] = {}
    for row in rows:
        tournament_info[row["id"]] = {
            "id": row["id"],
            "name": row["name"],
            "source": row["source"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "detail_url": row["detail_url"],
            "status": row["status"],
        }

    team_map: dict[str, dict[str, Any]] = {}

    for row in rows:
        tournament_id = row["id"]
        source = row["source"]
        try:
            division_teams: dict[str, list[dict[str, Any]]] = json.loads(row["division_teams"])
        except (json.JSONDecodeError, TypeError):
            continue

        for division, teams in division_teams.items():
            if _is_aggregate_key(division):
                continue
            if not division.upper().startswith(age_prefix):
                continue
            if not isinstance(teams, list):
                continue

            for team in teams:
                raw_name: str = team.get("team_name") or ""
                if not raw_name.strip():
                    continue

                key = raw_name.strip().lower()
                if key not in team_map:
                    team_map[key] = {
                        "team_name": raw_name.strip(),
                        "city_state": team.get("city_state") or "",
                        "sources": {},
                        "appearances": {},
                    }

                record_str = team.get("record") or ""
                parsed = parse_record(record_str)

                # One appearance entry per (team, tournament) — last write wins if seen twice
                team_map[key]["appearances"][tournament_id] = {
                    "record": record_str,
                    "has_record": parsed is not None,
                }

                if parsed is None:
                    continue

                wins, losses, ties = parsed
                src = team_map[key]["sources"].setdefault(
                    source, {"wins": 0, "losses": 0, "ties": 0}
                )
                src["wins"] += wins
                src["losses"] += losses
                src["ties"] += ties

    results: list[dict[str, Any]] = []
    for data in team_map.values():
        sources = data["sources"]
        total_wins = sum(s["wins"] for s in sources.values())
        total_losses = sum(s["losses"] for s in sources.values())
        total_ties = sum(s["ties"] for s in sources.values())
        total_games = total_wins + total_losses + total_ties
        win_pct = total_wins / total_games if total_games > 0 else 0.0

        def src_record(source_key: str, _sources: dict = sources) -> str:
            s = _sources.get(source_key)
            if not s:
                return ""
            return _format_record(s["wins"], s["losses"], s["ties"])

        appearances = [
            {**tournament_info[tid], "record": app_data["record"]}
            for tid, app_data in data["appearances"].items()
            if tid in tournament_info
        ]
        appearances.sort(key=lambda x: x.get("start_date") or "")

        results.append({
            "team_name": data["team_name"],
            "city_state": data["city_state"],
            "ncs_record": src_record("ncs"),
            "usssa_record": src_record("usssa"),
            "perfect_game_record": src_record("perfect_game"),
            "cumulative_record": _format_record(total_wins, total_losses, total_ties),
            "win_pct": round(win_pct, 4),
            "total_games": total_games,
            "tournament_count": len(appearances),
            "appearances": appearances,
        })

    results.sort(key=lambda x: (-x["win_pct"], -x["total_games"]))

    return {
        "age": age_division,
        "teams": results,
        "total_teams": len(results),
        "tournaments": list(tournament_info.values()),
        "note": (
            "Shows teams from tournaments marked Interested or Registered. "
            "Records only appear for tournaments whose team lists have been loaded."
        ),
    }
