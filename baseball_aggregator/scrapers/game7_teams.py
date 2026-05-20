"""Game7 team rankings scraper.

Scrapes team records from the Game7 Rankings page:
  https://www.game7baseball.com/baseball/Teams/Rankings?seasonId=<id>&ageId=<id>&classificationId=&state=

Supplements tournament-level team data for All Team Stats.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from baseball_aggregator.collectors.common import clean_text

AGE_TO_AGE_ID: dict[str, int] = {
    "7U": 1,
    "8U": 2,
    "9U": 3,
    "10U": 4,
    "11U": 5,
    "12U": 6,
    "13U": 7,
    "14U": 8,
    "15U": 9,
    "16U": 10,
    "17U": 11,
    "18U": 12,
}

AGE_ID_TO_AGE: dict[int, str] = {v: k for k, v in AGE_TO_AGE_ID.items()}

# Update when Game7 rolls to a new season.
DEFAULT_SEASON_ID = 15

RANKINGS_BASE_URL = "https://www.game7baseball.com/baseball/Teams/Rankings"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_rankings_page(html: str, age_division: str, state: str) -> list[dict[str, Any]]:
    """Parse a Game7 Rankings page into a list of team dicts.

    Returns a list of dicts with keys:
        team_name, city_state, record, age_division, division, state
    """
    soup = BeautifulSoup(html, "html.parser")
    age_prefix = age_division.strip().upper()
    teams: list[dict[str, Any]] = []

    # Try panel-based layout first (same platform as NCS)
    container = soup.select_one("#whosComingContainer") or soup
    panels = container.select(".panel")
    if panels:
        for panel in panels:
            division_el = panel.select_one(".panel-heading .division")
            if division_el is None:
                heading = panel.select_one(".panel-heading")
                if heading is None:
                    continue
                division_text = clean_text(heading.get_text())
            else:
                division_text = clean_text(division_el.get_text())

            if not division_text:
                continue
            if not division_text.upper().startswith(age_prefix):
                continue

            for row_team in _parse_panel_rows(panel, division_text, state):
                teams.append(row_team)
        return teams

    # Fallback: flat table (Rankings pages sometimes render without panels)
    for table in soup.select("table"):
        for row_team in _parse_flat_table_rows(table, age_prefix, state):
            teams.append(row_team)
    return teams


def _parse_panel_rows(panel: Tag, division: str, state: str) -> list[dict[str, Any]]:
    teams: list[dict[str, Any]] = []
    headers = [
        clean_text(th.get_text()).lower().replace("-", "_").replace("/", "_")
        for th in panel.select("table thead th")
    ]

    for row in panel.select("table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        team_index = _col_index(headers, "team name", 1)
        team_cell = cells[team_index] if team_index < len(cells) else cells[1]
        team_link = team_cell.select_one("a[href]")
        team_name = clean_text(team_link.get_text() if team_link else team_cell.get_text())

        if team_name.lower() == "open" and team_link is None:
            continue
        if not team_name:
            continue

        city_state_idx = _col_index(headers, "city_state", 3)
        city_state = clean_text(cells[city_state_idx].get_text()) if city_state_idx < len(cells) else ""
        record_idx = _col_index(headers, "w_l_t", len(cells) - 1)
        record = clean_text(cells[record_idx].get_text()) if record_idx < len(cells) else ""

        teams.append({
            "team_name": team_name,
            "city_state": city_state,
            "record": record,
            "division": division,
            "state": state,
        })
    return teams


def _parse_flat_table_rows(table: Tag, age_prefix: str, state: str) -> list[dict[str, Any]]:
    """Parse a Rankings-style table that isn't wrapped in panels."""
    teams: list[dict[str, Any]] = []
    headers = [
        clean_text(th.get_text()).lower().replace("-", "_").replace("/", "_")
        for th in table.select("thead th")
    ]
    if not headers:
        return teams

    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        age_idx = _col_index(headers, "age", -1)
        if age_idx >= 0 and age_idx < len(cells):
            row_age = clean_text(cells[age_idx].get_text()).upper()
            if not row_age.startswith(age_prefix):
                continue

        division_idx = _col_index(headers, "division", -1)
        division = clean_text(cells[division_idx].get_text()) if 0 <= division_idx < len(cells) else ""

        team_index = _col_index(headers, "team name", 1)
        team_cell = cells[team_index] if team_index < len(cells) else cells[1]
        team_link = team_cell.select_one("a[href]")
        team_name = clean_text(team_link.get_text() if team_link else team_cell.get_text())
        if not team_name:
            continue

        city_state_idx = _col_index(headers, "city_state", -1)
        city_state = clean_text(cells[city_state_idx].get_text()) if 0 <= city_state_idx < len(cells) else ""
        record_idx = _col_index(headers, "w_l_t", len(cells) - 1)
        record = clean_text(cells[record_idx].get_text()) if record_idx < len(cells) else ""

        teams.append({
            "team_name": team_name,
            "city_state": city_state,
            "record": record,
            "division": division,
            "state": state,
        })
    return teams


def _col_index(headers: list[str], name: str, default: int) -> int:
    normalized = name.lower().replace("-", "_").replace("/", "_")
    try:
        return headers.index(normalized)
    except ValueError:
        return default


def fetch_rankings_html(
    age_division: str,
    season_id: int = DEFAULT_SEASON_ID,
    state: str = "",
    classification_id: str = "",
    client: httpx.Client | None = None,
) -> str:
    age_id = AGE_TO_AGE_ID.get(age_division.strip().upper())
    if age_id is None:
        raise ValueError(
            f"Unknown age division {age_division!r}. "
            f"Supported values: {sorted(AGE_TO_AGE_ID)}"
        )

    params: dict[str, Any] = {
        "seasonId": season_id,
        "ageId": age_id,
        "classificationId": classification_id,
        "state": state.upper() if state else "",
    }

    own_client = client is None
    if own_client:
        client = httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True)
    try:
        response = client.get(RANKINGS_BASE_URL, params=params)
        response.raise_for_status()
        return response.text
    finally:
        if own_client:
            client.close()


def init_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS game7_team_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL,
            city_state TEXT NOT NULL DEFAULT '',
            record TEXT NOT NULL DEFAULT '',
            division TEXT NOT NULL DEFAULT '',
            age_division TEXT NOT NULL,
            state TEXT NOT NULL,
            season_id INTEGER NOT NULL,
            scraped_at TEXT NOT NULL,
            UNIQUE(team_name, age_division, state, season_id)
        )
        """
    )


def upsert_records(
    conn: sqlite3.Connection,
    teams: list[dict[str, Any]],
    age_division: str,
    state: str,
    season_id: int = DEFAULT_SEASON_ID,
) -> int:
    init_table(conn)
    now = datetime.now(UTC).isoformat()
    count = 0
    for team in teams:
        conn.execute(
            """
            INSERT INTO game7_team_records
                (team_name, city_state, record, division, age_division, state, season_id, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_name, age_division, state, season_id) DO UPDATE SET
                city_state = excluded.city_state,
                record = excluded.record,
                division = excluded.division,
                scraped_at = excluded.scraped_at
            """,
            (
                team["team_name"],
                team.get("city_state") or "",
                team.get("record") or "",
                team.get("division") or "",
                age_division.strip().upper(),
                state.upper(),
                season_id,
                now,
            ),
        )
        count += 1
    conn.commit()
    return count


def scrape_game7_teams(
    conn: sqlite3.Connection,
    age_division: str,
    season_id: int = DEFAULT_SEASON_ID,
    state: str = "",
    client: httpx.Client | None = None,
    team_id: str | None = None,
) -> dict[str, Any]:
    """Scrape Game7 team rankings and upsert into the DB."""
    from baseball_aggregator.stats import current_season_year
    from baseball_aggregator.storage import upsert_team_records

    html = fetch_rankings_html(age_division, season_id=season_id, state=state, client=client)
    teams = parse_rankings_page(html, age_division, state)
    upserted = upsert_records(conn, teams, age_division, state, season_id)

    if team_id and teams:
        season = current_season_year()
        unified_records = [
            {
                "source": "game7",
                "team_name": t["team_name"],
                "age_division": age_division.strip().upper(),
                "season": season,
                "wins": _wins(t.get("record") or ""),
                "losses": _losses(t.get("record") or ""),
                "ties": _ties(t.get("record") or ""),
                "detail_url": "",
            }
            for t in teams
        ]
        upsert_team_records(conn, team_id, unified_records)

    return {
        "age_division": age_division.strip().upper(),
        "season_id": season_id,
        "state": state.upper() if state else "",
        "teams_found": len(teams),
        "teams_upserted": upserted,
    }


def _wins(record: str) -> int:
    m = re.match(r"(\d+)-", record)
    return int(m.group(1)) if m else 0


def _losses(record: str) -> int:
    m = re.match(r"\d+-(\d+)", record)
    return int(m.group(1)) if m else 0


def _ties(record: str) -> int:
    m = re.match(r"\d+-\d+-(\d+)", record)
    return int(m.group(1)) if m else 0
