"""NCS team record scraper.

Scrapes team records directly from the NCS Teams listing page:
  https://www.playncs.com/baseball/Teams?seasonId=<id>&country=US&state=<ST>&ageId=<id>

This supplements tournament-level team data: teams that appear in NCS registered
tournaments but whose records aren't yet hydrated via the WhosComing endpoint will
still show up in All Team Stats via this scraper.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from baseball_aggregator.collectors.common import clean_text

# ---------------------------------------------------------------------------
# Age division ↔ NCS ageId mapping
# Source: observed from playncs.com URL parameters; ageId=2 == 8U confirmed by user.
# ---------------------------------------------------------------------------
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

# The NCS season ID for the current (2025-2026) season.
# Update this when NCS rolls to a new season.
DEFAULT_SEASON_ID = 29

TEAMS_BASE_URL = "https://www.playncs.com/baseball/Teams"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# HTML parser — same table structure as NCS WhosComing
# ---------------------------------------------------------------------------

def parse_teams_page(html: str, age_division: str, state: str) -> list[dict[str, Any]]:
    """Parse an NCS Teams listing page and return a list of team dicts.

    The page uses the same ``#whosComingContainer`` + panel structure as the
    WhosComing page.  Each panel has a heading with the division name and a
    table body with one row per team.

    Returns a list of dicts with keys:
        team_name, city_state, record, age_division, division, state
    """
    soup = BeautifulSoup(html, "html.parser")
    age_prefix = age_division.strip().upper()
    teams: list[dict[str, Any]] = []

    # The Teams page may use #whosComingContainer (same template) or just
    # render panels at the top level.  Support both.
    container = soup.select_one("#whosComingContainer") or soup
    for panel in container.select(".panel"):
        division_el = panel.select_one(".panel-heading .division")
        if division_el is None:
            # Fallback: look for any heading text inside the panel heading
            heading = panel.select_one(".panel-heading")
            if heading is None:
                continue
            division_text = clean_text(heading.get_text())
        else:
            division_text = clean_text(division_el.get_text())

        if not division_text:
            continue
        # Only include divisions matching the requested age prefix
        if not division_text.upper().startswith(age_prefix):
            continue

        for row_team in _parse_panel_rows(panel, division_text, state):
            teams.append(row_team)

    return teams


def _parse_panel_rows(panel: Tag, division: str, state: str) -> list[dict[str, Any]]:
    """Extract team rows from a single division panel."""
    teams: list[dict[str, Any]] = []
    headers = [
        clean_text(th.get_text()).lower().replace("-", "_").replace("/", "_")
        for th in panel.select("table thead th")
    ]

    for row in panel.select("table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # Team name — may be inside an <a> tag
        team_index = _col_index(headers, "team name", 1)
        team_cell = cells[team_index] if team_index < len(cells) else cells[1]
        team_link = team_cell.select_one("a[href]")
        team_name = clean_text(team_link.get_text() if team_link else team_cell.get_text())

        # Skip placeholder "Open" slots with no link
        if team_name.lower() == "open" and team_link is None:
            continue
        if not team_name:
            continue

        city_state = clean_text(
            cells[_col_index(headers, "city_state", 3)].get_text()
            if _col_index(headers, "city_state", 3) < len(cells)
            else ""
        )
        record = clean_text(
            cells[_col_index(headers, "w_l_t", len(cells) - 1)].get_text()
            if _col_index(headers, "w_l_t", len(cells) - 1) < len(cells)
            else ""
        )

        teams.append(
            {
                "team_name": team_name,
                "city_state": city_state,
                "record": record,
                "division": division,
                "state": state,
            }
        )
    return teams


def _col_index(headers: list[str], name: str, default: int) -> int:
    normalized = name.lower().replace("-", "_").replace("/", "_")
    try:
        return headers.index(normalized)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def fetch_teams_html(
    state: str,
    age_division: str,
    season_id: int = DEFAULT_SEASON_ID,
    client: httpx.Client | None = None,
) -> str:
    """Fetch the raw HTML for the NCS Teams page for a given state + age.

    Raises ``httpx.HTTPStatusError`` on non-2xx responses.
    """
    age_id = AGE_TO_AGE_ID.get(age_division.strip().upper())
    if age_id is None:
        raise ValueError(
            f"Unknown age division {age_division!r}. "
            f"Supported values: {sorted(AGE_TO_AGE_ID)}"
        )

    params = {
        "seasonId": season_id,
        "country": "US",
        "state": state.upper(),
        "ageId": age_id,
    }

    own_client = client is None
    if own_client:
        client = httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True)
    try:
        response = client.get(TEAMS_BASE_URL, params=params)
        response.raise_for_status()
        return response.text
    finally:
        if own_client:
            client.close()


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def init_ncs_team_records_table(conn: sqlite3.Connection) -> None:
    """Create the ncs_team_records table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ncs_team_records (
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


def upsert_ncs_team_records(
    conn: sqlite3.Connection,
    teams: list[dict[str, Any]],
    age_division: str,
    state: str,
    season_id: int = DEFAULT_SEASON_ID,
) -> int:
    """Upsert scraped NCS team records into ncs_team_records.

    Returns the number of rows inserted or replaced.
    """
    init_ncs_team_records_table(conn)
    now = datetime.now(UTC).isoformat()
    count = 0
    for team in teams:
        conn.execute(
            """
            INSERT INTO ncs_team_records
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


def get_ncs_team_records(
    conn: sqlite3.Connection,
    age_division: str,
) -> list[dict[str, Any]]:
    """Return all scraped NCS team records for an age division."""
    init_ncs_team_records_table(conn)
    age_prefix = age_division.strip().upper()
    rows = conn.execute(
        "SELECT * FROM ncs_team_records WHERE age_division = ? ORDER BY team_name",
        (age_prefix,),
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# High-level scrape entry point
# ---------------------------------------------------------------------------

def scrape_ncs_teams(
    conn: sqlite3.Connection,
    state: str,
    age_division: str,
    season_id: int = DEFAULT_SEASON_ID,
    client: httpx.Client | None = None,
    team_id: str | None = None,
) -> dict[str, Any]:
    """Scrape NCS teams for a state + age division and upsert into the DB.

    Returns a summary dict with ``teams_found`` and ``teams_upserted``.
    If ``team_id`` is provided, results are also written to the unified
    ``team_records`` table.
    """
    from baseball_aggregator.stats import current_season_year
    from baseball_aggregator.storage import upsert_team_records

    html = fetch_teams_html(state, age_division, season_id=season_id, client=client)
    teams = parse_teams_page(html, age_division, state)
    upserted = upsert_ncs_team_records(conn, teams, age_division, state, season_id)

    if team_id and teams:
        season = current_season_year()
        unified_records = [
            {
                "source":       "ncs",
                "team_name":    t["team_name"],
                "age_division": age_division.strip().upper(),
                "season":       season,
                "wins":         _parse_record_wins(t.get("record") or ""),
                "losses":       _parse_record_losses(t.get("record") or ""),
                "ties":         _parse_record_ties(t.get("record") or ""),
                "detail_url":   "",
            }
            for t in teams
        ]
        upsert_team_records(conn, team_id, unified_records)

    return {
        "state": state.upper(),
        "age_division": age_division.strip().upper(),
        "season_id": season_id,
        "teams_found": len(teams),
        "teams_upserted": upserted,
    }


def _parse_record_wins(record: str) -> int:
    import re
    m = re.match(r"(\d+)-", record)
    return int(m.group(1)) if m else 0


def _parse_record_losses(record: str) -> int:
    import re
    m = re.match(r"\d+-(\d+)", record)
    return int(m.group(1)) if m else 0


def _parse_record_ties(record: str) -> int:
    import re
    m = re.match(r"\d+-\d+-(\d+)", record)
    return int(m.group(1)) if m else 0
