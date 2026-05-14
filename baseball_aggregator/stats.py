from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any


def current_season_year() -> str:
    """Return the ending year of the current baseball season.

    Seasons run Fall–Summer labeled by the ending year.
    August cutover: month >= 8 means the Fall semester of the new season has begun.
    """
    now = datetime.now()
    return str(now.year + 1 if now.month >= 8 else now.year)


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
    return f"{wins}-{losses}-{ties}"


def aggregate_team_records(
    conn: sqlite3.Connection,
    team_id: str,
    age_division: str,
    season: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate W-L-T records for all teams.

    Reads from the unified ``team_records`` table when data is available
    (populated by the stats worker). Falls back to ``division_teams`` JSON
    and ``ncs_team_records`` for sources that haven't been enriched yet.

    Groups teams by normalized name, keeps the best record per source,
    and returns a list sorted by win% descending (then total games descending).
    """
    from baseball_aggregator.storage import get_team_records

    if season is None:
        season = current_season_year()

    age_prefix = age_division.strip().upper()

    # Keyed by normalized team name
    team_map: dict[str, dict[str, Any]] = {}

    # --- Primary path: unified team_records table ---
    unified = get_team_records(conn, team_id, season=season)
    # Normalize age_division for filtering (partial prefix match)
    unified_filtered = [
        r for r in unified
        if (r.get("age_division") or "").upper().startswith(age_prefix)
        or age_prefix in (r.get("age_division") or "").upper()
    ]
    sources_in_unified: set[str] = set()
    for r in unified_filtered:
        sources_in_unified.add(r["source"])
        raw_name: str = r["team_name"] or ""
        if not raw_name.strip():
            continue
        key = raw_name.strip().lower()
        if key not in team_map:
            team_map[key] = {"team_name": raw_name.strip(), "city_state": "", "sources": {}}
        src = r["source"]
        wins, losses, ties = int(r["wins"]), int(r["losses"]), int(r["ties"])
        total = wins + losses + ties
        existing = team_map[key]["sources"].get(src)
        if existing is None or total > existing["wins"] + existing["losses"] + existing["ties"]:
            team_map[key]["sources"][src] = {"wins": wins, "losses": losses, "ties": ties}

    # --- Fallback path: division_teams JSON (sources not yet in team_records) ---
    # Only runs for sources that have no data in team_records yet.
    fallback_sources = {"ncs", "usssa", "perfect_game"} - sources_in_unified
    if fallback_sources:
        rows = conn.execute(
            "SELECT source, division_teams FROM tournaments WHERE division_teams != '{}'",
        ).fetchall()
        for row in rows:
            source = row["source"]
            if source not in fallback_sources:
                continue
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
                    raw_name = team.get("team_name") or ""
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
                    total = wins + losses + ties
                    existing = team_map[key]["sources"].get(source)
                    if existing is None or total > existing["wins"] + existing["losses"] + existing["ties"]:
                        team_map[key]["sources"][source] = {"wins": wins, "losses": losses, "ties": ties}

        # Also pull from ncs_team_records if NCS not yet in team_records
        if "ncs" in fallback_sources:
            _merge_ncs_team_records(conn, age_prefix, team_map)

    results: list[dict[str, Any]] = []
    for data in team_map.values():
        sources = data["sources"]
        total_wins   = sum(s["wins"]   for s in sources.values())
        total_losses = sum(s["losses"] for s in sources.values())
        total_ties   = sum(s["ties"]   for s in sources.values())
        total_games  = total_wins + total_losses + total_ties
        win_pct = total_wins / total_games if total_games > 0 else 0.0

        def src_record(source_key: str) -> str:
            s = sources.get(source_key)
            if not s:
                return ""
            return _format_record(s["wins"], s["losses"], s["ties"])

        results.append({
            "team_name":            data["team_name"],
            "city_state":           data["city_state"],
            "ncs_record":           src_record("ncs"),
            "usssa_record":         src_record("usssa"),
            "perfect_game_record":  src_record("perfect_game"),
            "grand_slam_record":    src_record("grand_slam"),
            "game7_record":         src_record("game7"),
            "cumulative_record":    _format_record(total_wins, total_losses, total_ties),
            "win_pct":              round(win_pct, 4),
            "total_games":          total_games,
            "sources_seen":         list(sources.keys()),
        })

    results.sort(key=lambda x: (-x["win_pct"], -x["total_games"]))
    return results


def _merge_ncs_team_records(
    conn: sqlite3.Connection,
    age_prefix: str,
    team_map: dict[str, dict[str, Any]],
) -> None:
    """Merge records from ncs_team_records into team_map (mutates in place).

    Skips gracefully if the table doesn't exist yet (first run before any
    NCS Teams scrape has been triggered).
    """
    try:
        ncs_rows = conn.execute(
            "SELECT team_name, city_state, record FROM ncs_team_records WHERE age_division = ?",
            (age_prefix,),
        ).fetchall()
    except Exception:
        # Table may not exist yet — that's fine, just skip.
        return

    for row in ncs_rows:
        raw_name: str = row["team_name"] or ""
        if not raw_name.strip():
            continue

        record_str: str = row["record"] or ""
        parsed = parse_record(record_str)
        if parsed is None:
            continue

        key = raw_name.strip().lower()
        if key not in team_map:
            team_map[key] = {
                "team_name": raw_name.strip(),
                "city_state": row["city_state"] or "",
                "sources": {},
            }
        # Fill city_state if the tournament path left it blank
        if not team_map[key]["city_state"] and row["city_state"]:
            team_map[key]["city_state"] = row["city_state"]

        wins, losses, ties = parsed
        src = team_map[key]["sources"].setdefault(
            "ncs", {"wins": 0, "losses": 0, "ties": 0}
        )
        src["wins"] += wins
        src["losses"] += losses
        src["ties"] += ties


def team_analysis_records(
    conn: sqlite3.Connection,
    age_division: str,
    team_id: str = "",
    season: str | None = None,
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
                total = wins + losses + ties
                existing = team_map[key]["sources"].get(source)
                if existing is None or total > existing["wins"] + existing["losses"] + existing["ties"]:
                    team_map[key]["sources"][source] = {"wins": wins, "losses": losses, "ties": ties}

    # Augment team_map from team_records table before building results
    if team_id:
        from baseball_aggregator.storage import get_team_records
        effective_season = season or current_season_year()
        unified = get_team_records(conn, team_id, season=effective_season)
        unified_age = [
            r for r in unified
            if (r.get("age_division") or "").upper().startswith(age_prefix)
            or age_prefix in (r.get("age_division") or "").upper()
        ]
        for r in unified_age:
            raw_name: str = r["team_name"] or ""
            key = raw_name.strip().lower()
            if key not in team_map:
                continue
            src = r["source"]
            wins, losses, ties = int(r["wins"]), int(r["losses"]), int(r["ties"])
            total = wins + losses + ties
            existing = team_map[key]["sources"].get(src)
            if existing is None or total > existing["wins"] + existing["losses"] + existing["ties"]:
                team_map[key]["sources"][src] = {"wins": wins, "losses": losses, "ties": ties}

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
            "grand_slam_record": src_record("grand_slam"),
            "game7_record": src_record("game7"),
            "cumulative_record": _format_record(total_wins, total_losses, total_ties),
            "win_pct": round(win_pct, 4),
            "total_games": total_games,
            "tournament_count": len(appearances),
            "appearances": appearances,
        })

    results.sort(key=lambda x: (-x["win_pct"], -x["total_games"]))

    return {
        "age": age_division,
        "season": season or current_season_year(),
        "teams": results,
        "total_teams": len(results),
        "tournaments": list(tournament_info.values()),
    }
