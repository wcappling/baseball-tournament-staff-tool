"""Tests for the NCS Teams scraper and its integration with aggregate_team_records."""
from __future__ import annotations

import sqlite3

import pytest

from baseball_aggregator.scrapers.ncs_teams import (
    AGE_TO_AGE_ID,
    DEFAULT_SEASON_ID,
    get_ncs_team_records,
    init_ncs_team_records_table,
    parse_teams_page,
    upsert_ncs_team_records,
)
from baseball_aggregator.stats import aggregate_team_records
from baseball_aggregator.storage import init_db


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_TEAMS_HTML = """
<!doctype html>
<html><body>
  <div id="whosComingContainer">
    <div class="panel">
      <div class="panel-heading">
        <div class="division">8U OPEN</div>
        <div class="registered"><div>3 Teams Registered</div></div>
      </div>
      <div class="panel-body">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Team Name</th>
              <th>Confirmed</th>
              <th>Division</th>
              <th>City/State</th>
              <th>W-L-T</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1</td>
              <td><a href="/baseball/Teams/Details/10/team-alpha">Alpha 8U</a></td>
              <td><i class="fa fa-check"></i></td>
              <td>8U OPEN</td>
              <td>Huntsville, AL</td>
              <td>5-2-0</td>
            </tr>
            <tr>
              <td>2</td>
              <td><a href="/baseball/Teams/Details/11/team-beta">Beta Baseball</a></td>
              <td></td>
              <td>8U OPEN</td>
              <td>Madison, AL</td>
              <td>3-4-1</td>
            </tr>
            <tr>
              <td>3</td>
              <td>Open</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="panel">
      <div class="panel-heading">
        <div class="division">9U OPEN</div>
        <div class="registered"><div>1 Team Registered</div></div>
      </div>
      <div class="panel-body">
        <table>
          <thead>
            <tr><th>#</th><th>Team Name</th><th>Confirmed</th><th>Division</th><th>City/State</th><th>W-L-T</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>1</td>
              <td><a href="/baseball/Teams/Details/20/team-gamma">Gamma 9U</a></td>
              <td></td>
              <td>9U OPEN</td>
              <td>Decatur, AL</td>
              <td>1-0-0</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</body></html>
"""


def _in_memory_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# parse_teams_page tests
# ---------------------------------------------------------------------------

def test_parse_teams_page_returns_only_matching_age():
    teams = parse_teams_page(SAMPLE_TEAMS_HTML, "8U", "AL")
    # Should include 8U OPEN teams but NOT 9U OPEN
    assert len(teams) == 2
    names = [t["team_name"] for t in teams]
    assert "Alpha 8U" in names
    assert "Beta Baseball" in names
    assert all("Gamma" not in n for n in names)


def test_parse_teams_page_extracts_fields():
    teams = parse_teams_page(SAMPLE_TEAMS_HTML, "8U", "AL")
    alpha = next(t for t in teams if t["team_name"] == "Alpha 8U")
    assert alpha["city_state"] == "Huntsville, AL"
    assert alpha["record"] == "5-2-0"
    assert alpha["division"] == "8U OPEN"
    assert alpha["state"] == "AL"


def test_parse_teams_page_skips_open_placeholders():
    teams = parse_teams_page(SAMPLE_TEAMS_HTML, "8U", "AL")
    assert all(t["team_name"] != "Open" for t in teams)


def test_parse_teams_page_handles_ties():
    teams = parse_teams_page(SAMPLE_TEAMS_HTML, "8U", "AL")
    beta = next(t for t in teams if t["team_name"] == "Beta Baseball")
    assert beta["record"] == "3-4-1"


def test_parse_teams_page_empty_when_no_matching_age():
    teams = parse_teams_page(SAMPLE_TEAMS_HTML, "14U", "AL")
    assert teams == []


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

def test_upsert_and_get_ncs_team_records():
    conn = _in_memory_conn()
    init_ncs_team_records_table(conn)

    teams = [
        {"team_name": "Alpha 8U", "city_state": "Huntsville, AL", "record": "5-2-0", "division": "8U OPEN"},
        {"team_name": "Beta Baseball", "city_state": "Madison, AL", "record": "3-4-1", "division": "8U OPEN"},
    ]
    count = upsert_ncs_team_records(conn, teams, "8U", "AL", DEFAULT_SEASON_ID)
    assert count == 2

    records = get_ncs_team_records(conn, "8U")
    assert len(records) == 2
    alpha = next(r for r in records if r["team_name"] == "Alpha 8U")
    assert alpha["record"] == "5-2-0"
    assert alpha["state"] == "AL"
    assert alpha["age_division"] == "8U"


def test_upsert_ncs_team_records_updates_on_conflict():
    conn = _in_memory_conn()
    init_ncs_team_records_table(conn)

    teams = [{"team_name": "Alpha 8U", "city_state": "Huntsville, AL", "record": "5-2-0", "division": "8U OPEN"}]
    upsert_ncs_team_records(conn, teams, "8U", "AL", DEFAULT_SEASON_ID)

    # Second upsert with updated record
    teams2 = [{"team_name": "Alpha 8U", "city_state": "Huntsville, AL", "record": "7-2-0", "division": "8U OPEN"}]
    upsert_ncs_team_records(conn, teams2, "8U", "AL", DEFAULT_SEASON_ID)

    records = get_ncs_team_records(conn, "8U")
    assert len(records) == 1
    assert records[0]["record"] == "7-2-0"


def test_get_ncs_team_records_filters_by_age():
    conn = _in_memory_conn()
    init_ncs_team_records_table(conn)

    teams_8u = [{"team_name": "Team 8U", "city_state": "AL", "record": "1-0-0", "division": "8U OPEN"}]
    teams_12u = [{"team_name": "Team 12U", "city_state": "AL", "record": "2-1-0", "division": "12U OPEN"}]
    upsert_ncs_team_records(conn, teams_8u, "8U", "AL", DEFAULT_SEASON_ID)
    upsert_ncs_team_records(conn, teams_12u, "12U", "AL", DEFAULT_SEASON_ID)

    records_8u = get_ncs_team_records(conn, "8U")
    assert len(records_8u) == 1
    assert records_8u[0]["team_name"] == "Team 8U"


# ---------------------------------------------------------------------------
# aggregate_team_records integration
# ---------------------------------------------------------------------------

def test_aggregate_includes_ncs_team_records():
    """Teams in ncs_team_records appear in aggregate_team_records output."""
    conn = _in_memory_conn()
    init_db(conn)

    teams = [
        {"team_name": "Alpha 8U", "city_state": "Huntsville, AL", "record": "5-2-0", "division": "8U OPEN"},
    ]
    upsert_ncs_team_records(conn, teams, "8U", "AL", DEFAULT_SEASON_ID)

    results = aggregate_team_records(conn, "8U")
    names = [r["team_name"] for r in results]
    assert "Alpha 8U" in names

    alpha = next(r for r in results if r["team_name"] == "Alpha 8U")
    assert alpha["ncs_record"] == "5-2-0"
    assert "ncs" in alpha["sources_seen"]


def test_aggregate_merges_ncs_records_with_tournament_data():
    """When a team has both tournament-hydrated and directly-scraped NCS records,
    wins and losses accumulate under the 'ncs' source."""
    from baseball_aggregator.models import Tournament
    from baseball_aggregator.storage import upsert_tournaments

    conn = _in_memory_conn()
    init_db(conn)

    # Insert a tournament with an NCS record for Alpha 8U
    upsert_tournaments(
        conn,
        [
            Tournament(
                source="ncs",
                source_id="999",
                name="Test Tournament",
                detail_url="https://example.com",
                location="Huntsville, AL",
                age_divisions=["8U OPEN"],
                division_teams={
                    "8U OPEN": [
                        {
                            "team_name": "Alpha 8U",
                            "city_state": "Huntsville, AL",
                            "record": "3-1-0",
                            "confirmed": True,
                            "division": "8U OPEN",
                        }
                    ]
                },
                division_team_counts={"8U OPEN": 1, "8U": 1},
                team_count_scope="division",
            )
        ],
    )

    # Also insert a directly-scraped NCS record (season-wide record)
    upsert_ncs_team_records(
        conn,
        [{"team_name": "Alpha 8U", "city_state": "Huntsville, AL", "record": "2-1-0", "division": "8U OPEN"}],
        "8U",
        "AL",
        DEFAULT_SEASON_ID,
    )

    results = aggregate_team_records(conn, "8U")
    alpha = next((r for r in results if r["team_name"] == "Alpha 8U"), None)
    assert alpha is not None
    # 3-1 from tournament + 2-1 from direct scrape = 5-2 under ncs
    assert alpha["ncs_record"] == "5-2-0"
    assert alpha["total_games"] == 7


# ---------------------------------------------------------------------------
# Age ID mapping tests
# ---------------------------------------------------------------------------

def test_age_to_age_id_mapping_includes_common_ages():
    assert AGE_TO_AGE_ID["8U"] == 2
    assert AGE_TO_AGE_ID["12U"] == 6


def test_age_to_age_id_mapping_covers_7u_through_18u():
    for age_num in range(7, 19):
        age = f"{age_num}U"
        assert age in AGE_TO_AGE_ID, f"{age} missing from AGE_TO_AGE_ID"
