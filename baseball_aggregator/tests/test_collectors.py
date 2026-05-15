from datetime import date
from pathlib import Path

from baseball_aggregator.collectors.common import parse_date_range
from baseball_aggregator.collectors.registry import list_collectors
from baseball_aggregator.collectors.ncs import (
    parse_event_list as parse_ncs,
    parse_whos_coming,
    parse_whos_coming_counts,
    whos_coming_url,
)
from unittest.mock import MagicMock, patch

from baseball_aggregator.collectors.perfect_game import parse_event_list as parse_pg
from baseball_aggregator.collectors.perfect_game import parse_api_results as parse_pg_api
from baseball_aggregator.collectors.perfect_game import parse_tournament_teams as parse_pg_teams
from baseball_aggregator.collectors.perfect_game import enrich_with_team_lists as pg_enrich
from baseball_aggregator.collectors.usssa import parse_division_results as parse_usssa_divisions
from baseball_aggregator.collectors.usssa import parse_event_list as parse_usssa
from baseball_aggregator.collectors.usssa import parse_seeding_report_teams as parse_usssa_teams
from baseball_aggregator.collectors.usssa import enrich_with_seeding_reports as usssa_enrich
from baseball_aggregator.collectors.usssa import parse_usssa_age_division

FIXTURES = Path(__file__).parent / "fixtures"


def test_ncs_parser():
    tournaments = parse_ncs((FIXTURES / "ncs_sample_page1.html").read_text(encoding="utf-8"))
    assert len(tournaments) == 2
    assert tournaments[0].source == "ncs"
    assert tournaments[0].source_id == "12198"
    assert tournaments[0].location == "Cullman, AL"
    assert tournaments[0].registered_teams == 55
    assert "12U" in tournaments[0].age_divisions


def test_ncs_whos_coming_counts_are_aggregated_by_age():
    html = (FIXTURES / "ncs_whoscoming_sample.html").read_text(encoding="utf-8")
    counts = parse_whos_coming_counts(html)
    assert counts["11U OPEN"] == 2
    assert counts["11U"] == 2
    assert counts["12U D2"] == 3
    assert counts["12U OPEN"] == 2
    assert counts["12U"] == 5


def test_ncs_whos_coming_extracts_team_rows_when_registration_is_closed():
    html = (FIXTURES / "ncs_whoscoming_sample.html").read_text(encoding="utf-8")
    counts, teams = parse_whos_coming(html)
    assert counts["12U OPEN"] == 2
    assert [team["team_name"] for team in teams["12U OPEN"]] == ["Team D", "Team E"]
    assert teams["12U OPEN"][0]["record"] == "12-3-0"
    assert teams["12U OPEN"][0]["confirmed"] is True
    assert teams["12U OPEN"][1]["confirmed"] is False
    assert teams["12U OPEN"][0]["detail_url"].startswith("https://www.playncs.com/baseball/Teams/Details/4/")
    assert len(teams["12U"]) == 5
    assert all(team["team_name"] != "Open" for team in teams["12U"])


def test_ncs_whos_coming_url_from_detail_url():
    tournaments = parse_ncs((FIXTURES / "ncs_sample_page1.html").read_text(encoding="utf-8"))
    assert whos_coming_url(tournaments[0]) == (
        "https://www.playncs.com/baseball/Events/WhosComing/12198/"
        "2025-ncs-southeast-top-gun-super-nit"
    )


def test_usssa_parser():
    tournaments = parse_usssa((FIXTURES / "usssa_sample.html").read_text(encoding="utf-8"))
    assert len(tournaments) == 1
    assert tournaments[0].source == "usssa"
    assert tournaments[0].registered_teams == 8
    assert "12U" in tournaments[0].age_divisions


def test_usssa_api_results_parser():
    payload = {
        "results": [
            {
                "ID": 407473,
                "event_name": "Bat To The Future ($50)",
                "start_date": "2026-05-01T00:00:00",
                "end_date": "2026-05-03T00:00:00",
                "eventType": "Pool Play into 3GG",
                "eventDivisionsAll": "10U%Open|AA#12U%Open|AA#14U%AAA",
                "eventDirector": "Clay Richey - MS BB",
                "teamCount": "91",
                "stature": "USSSA NIT",
                "eventLocation": "OXFORD",
                "stateABR": "MS",
            }
        ]
    }
    tournaments = parse_usssa(__import__("json").dumps(payload))
    assert tournaments[0].source_id == "407473"
    assert tournaments[0].detail_url == "https://usssa.com/baseball/event_home/?eventID=407473"
    assert tournaments[0].location == "OXFORD, MS"
    assert tournaments[0].start_date == date(2026, 5, 1)
    assert tournaments[0].registered_teams == 91
    assert "12U OPEN" in tournaments[0].age_divisions


def test_usssa_division_counts_include_approved_entries():
    divisions = parse_usssa_divisions(
        [
            {"class": "12Op", "maxTeams": 12, "teamEntered": 12, "teamApproved": 10, "teamPending": 2, "minimum_number_games": 3, "entryFee": 50, "city": "Jackson", "eventFormat": "Pool to 3GG"},
            {"class": "12AA", "maxTeams": 12, "teamEntered": 20, "teamApproved": 18, "teamPending": 2, "minimum_number_games": 3, "entryFee": 50, "city": "Jackson", "eventFormat": "Pool to 3GG"},
            {"class": "14AAA60/90", "teamEntered": 9, "teamApproved": 9, "eventFormat": "Pool to 3GG"},
        ]
    )
    assert divisions["counts"]["12U OPEN"] == 12
    assert divisions["counts"]["12U AA"] == 20
    assert divisions["counts"]["12U"] == 32
    assert divisions["approved"]["12U"] == 28
    assert divisions["counts"]["14U AAA 60/90"] == 9
    assert divisions["details"]["12U OPEN"]["max_entries"] == 12
    assert divisions["details"]["12U OPEN"]["pending_entries"] == 2
    assert divisions["details"]["12U OPEN"]["min_games"] == 3
    assert divisions["details"]["12U OPEN"]["entry_fee"] == 50
    assert divisions["details"]["12U OPEN"]["location"] == "Jackson"


def test_usssa_seeding_report_team_parser():
    teams = parse_usssa_teams(
        {
            "seedingReport": {
                "notAvailable": False,
                "tournaments": [
                    {
                        "teamid": 3334794,
                        "teamcity": "Parsons",
                        "ManagerName": "Bryan Barnes",
                        "TeamState": "TN",
                        "TeamClass": "BBboys12AA",
                        "points": 50,
                        "Rating": 177,
                        "OverallWins": 0,
                        "OverallLoses": 3,
                        "Wins": 0,
                        "Loses": 2,
                        "teamname": "Panthers Baseball",
                    }
                ],
            }
        },
        "12U AA",
    )
    assert teams == [
        {
            "number": 1,
            "team_name": "Panthers Baseball",
            "confirmed": True,
            "division": "12U AA",
            "city_state": "TN - Parsons",
            "record": "0-3-0",
            "in_class_record": "0-2-0",
            "overall_record": "0-3-0",
            "team_class": "BBboys12AA",
            "manager_name": "Bryan Barnes",
            "points": 50,
            "rating": 177,
            "detail_url": "https://usssa.com/baseball/teamHome/?teamID=3334794",
        }
    ]


def test_perfect_game_parser():
    tournaments = parse_pg((FIXTURES / "perfect_game_sample.html").read_text(encoding="utf-8"))
    assert len(tournaments) == 1
    assert tournaments[0].source == "perfect_game"
    assert tournaments[0].registered_teams == 12
    assert "12U" in tournaments[0].age_divisions


def test_perfect_game_api_results_parser():
    tournaments = parse_pg_api(
        [
            {
                "eventgroupid": 22417,
                "eventschedulename": "2026 PG Southeast Spring Season Opener",
                "eventgrouplogo": "https://example.com/logo.png",
                "total_teams": 10,
                "eventprimaryballparkcity": "Marietta",
                "eventprimaryballparkstate": "GA",
                "circuit": "Signature",
                "events": [
                    {
                        "eventid": 137367,
                        "eventname": "2026 12U PG Southeast Spring Season Opener (MAJOR)",
                        "eventdivision": "12U",
                        "eventclassification": "Major",
                        "countteams": 6,
                        "eventtype": "PG Youth Tournament",
                        "eventstartdate": "2026-02-20",
                        "eventenddate": "2026-02-22",
                        "eventprimaryballparkcity": "Marietta",
                        "eventprimaryballparkstate": "GA",
                        "eventprimaryballparkname": "East Cobb Complex",
                        "director": "Southeast Youth",
                    },
                    {
                        "eventid": 137368,
                        "eventname": "2026 12U PG Southeast Spring Season Opener (MINOR)",
                        "eventdivision": "12U",
                        "eventclassification": "Minor",
                        "countteams": 4,
                        "eventtype": "PG Youth Tournament",
                        "eventstartdate": "2026-02-20",
                        "eventenddate": "2026-02-22",
                        "eventprimaryballparkcity": "Marietta",
                        "eventprimaryballparkstate": "GA",
                        "eventprimaryballparkname": "East Cobb Complex",
                    },
                ],
            }
        ]
    )
    assert len(tournaments) == 1
    assert tournaments[0].source_id == "22417"
    assert tournaments[0].location == "Marietta, GA"
    assert tournaments[0].registered_teams == 10
    assert tournaments[0].division_team_counts["12U MAJOR"] == 6
    assert tournaments[0].division_team_counts["12U MINOR"] == 4
    assert tournaments[0].division_team_counts["12U"] == 10
    assert tournaments[0].division_details["12U MAJOR"]["event_id"] == 137367


def test_perfect_game_team_parser():
    teams = parse_pg_teams(
        """
        <table>
          <tr><th>National Rank</th><th>Place</th><th>Team</th><th>Classification</th><th>From</th><th>Coach</th></tr>
          <tr>
            <td>1</td><td></td>
            <td><a href="Tournaments/Teams/Default.aspx?team=1011796">Wildcatters 12U Elite</a> (29-0-0 in 2026)</td>
            <td>12Major</td><td>Houston, TX</td><td>Cody Farr</td>
          </tr>
        </table>
        """,
        "12U MAJOR",
    )
    assert teams == [
        {
            "number": 1,
            "team_name": "Wildcatters 12U Elite",
            "confirmed": False,
            "division": "12U MAJOR",
            "city_state": "Houston, TX",
            "record": "29-0-0",
            "team_class": "12Major",
            "national_rank": "1",
            "manager_name": "Cody Farr",
            "detail_url": "https://www.perfectgame.org/Tournaments/Teams/Default.aspx?team=1011796",
        }
    ]


def test_planned_sources_are_registered():
    assert set(list_collectors()) == {"ncs", "usssa", "perfect_game", "grand_slam", "game7"}


# ── Grand Slam collector tests ──────────────────────────────────────────────

from baseball_aggregator.collectors.grand_slam import (
    parse_whos_coming as gs_parse_whos_coming,
    whos_coming_url as gs_whos_coming_url,
)
from baseball_aggregator.models import Tournament


def _gs_teams_html() -> str:
    return (FIXTURES / "grand_slam_teams_sample.html").read_text(encoding="utf-8")


def test_grand_slam_whos_coming_url():
    t = Tournament(
        source="grand_slam",
        source_id="4171",
        name="Test",
        detail_url="https://www.grandslamtournaments.com/baseball/Events/Details/4171/test-event",
    )
    assert gs_whos_coming_url(t) == (
        "https://www.grandslamtournaments.com/baseball/Events/Teams/4171/test-event"
    )


def test_grand_slam_whos_coming_url_fallback_uses_source_id():
    # When detail_url doesn't contain /Events/Details/, fall back to source_id
    t = Tournament(source="grand_slam", source_id="4171", name="X", detail_url="")
    assert gs_whos_coming_url(t) == "https://www.grandslamtournaments.com/baseball/Events/Teams/4171/"


def test_grand_slam_whos_coming_url_empty_when_no_source_id():
    t = Tournament(source="grand_slam", source_id="", name="X", detail_url="")
    assert gs_whos_coming_url(t) == ""


def test_grand_slam_parse_whos_coming_division_counts():
    counts, _ = gs_parse_whos_coming(_gs_teams_html())
    assert counts["8U-OPEN KP"] == 3   # 3 real teams (2 Open rows skipped)
    assert counts["8U-OPEN"] == 1
    assert counts["9U"] == 2           # bare age key — not double-counted
    # 8U aggregate: 3 (8U-OPEN KP) + 1 (8U-OPEN) = 4
    assert counts["8U"] == 4
    # 9U is bare key so should NOT produce a separate "9U" aggregate beyond itself
    assert counts.get("9U", 0) == 2


def test_grand_slam_parse_whos_coming_team_rows():
    counts, teams = gs_parse_whos_coming(_gs_teams_html())
    # 8U-OPEN KP has 3 teams, Open rows excluded
    assert len(teams["8U-OPEN KP"]) == 3
    names = [t["team_name"] for t in teams["8U-OPEN KP"]]
    assert "Alpha 8U" in names
    assert "Beta 8U" in names
    assert "Gamma 8U" in names
    assert "Open" not in names

    # Records are parsed correctly
    alpha = next(t for t in teams["8U-OPEN KP"] if t["team_name"] == "Alpha 8U")
    assert alpha["record"] == "5-2-0"
    assert alpha["city_state"] == "Huntsville, AL"
    assert alpha["detail_url"] == "https://www.grandslamtournaments.com/baseball/Teams/Details/28001/alpha-8u"

    beta = next(t for t in teams["8U-OPEN KP"] if t["team_name"] == "Beta 8U")
    assert beta["record"] == "3-4-1"


def test_grand_slam_parse_whos_coming_aggregate_rollup():
    counts, teams = gs_parse_whos_coming(_gs_teams_html())
    # 8U aggregate should contain teams from both 8U-OPEN KP and 8U-OPEN
    assert len(teams["8U"]) == 4
    all_names = [t["team_name"] for t in teams["8U"]]
    assert "Alpha 8U" in all_names
    assert "Zeta 8U" in all_names


def test_grand_slam_parse_whos_coming_no_double_count_for_bare_age_key():
    counts, teams = gs_parse_whos_coming(_gs_teams_html())
    # "9U" is a bare age key — the count should be 2, not 4 (double-counted)
    assert counts["9U"] == 2
    assert len(teams["9U"]) == 2


def test_date_parsing():
    today = date(2026, 4, 22)
    assert parse_date_range("Apr 25", today) == (date(2026, 4, 25), date(2026, 4, 25))
    assert parse_date_range("May 16-17", today) == (date(2026, 5, 16), date(2026, 5, 17))
    assert parse_date_range("Dec 30-Jan 2", today) == (date(2026, 12, 30), date(2027, 1, 2))


def test_perfect_game_enrich_populates_division_teams():
    """Verify pg_enrich calls fetch_tournament_teams per division and stores results."""
    tournaments = parse_pg_api(
        [
            {
                "eventgroupid": 22417,
                "eventschedulename": "2026 PG Southeast Spring Season Opener",
                "total_teams": 6,
                "eventprimaryballparkcity": "Marietta",
                "eventprimaryballparkstate": "GA",
                "events": [
                    {
                        "eventid": 137367,
                        "eventdivision": "12U",
                        "eventclassification": "Major",
                        "countteams": 6,
                        "eventstartdate": "2026-02-20",
                        "eventenddate": "2026-02-22",
                    }
                ],
            }
        ]
    )
    tournament = tournaments[0]
    assert tournament.division_teams.get("12U MAJOR") == []

    fake_teams = [{"team_name": "Wildcatters 12U Elite", "record": "29-0-0", "division": "12U MAJOR"}]
    client = MagicMock()
    with patch(
        "baseball_aggregator.collectors.perfect_game.fetch_tournament_teams",
        return_value=fake_teams,
    ) as mock_fetch:
        pg_enrich(tournament, client, target_age="12U")
        mock_fetch.assert_called_once_with(client, "137367", "12U MAJOR")

    assert tournament.division_teams["12U MAJOR"] == fake_teams
    assert fake_teams[0] in tournament.division_teams.get("12U", [])


def test_perfect_game_enrich_skips_failed_requests():
    """Verify pg_enrich handles HTTP errors gracefully without crashing."""
    import httpx

    tournaments = parse_pg_api(
        [
            {
                "eventgroupid": 22417,
                "eventschedulename": "Test Tournament",
                "total_teams": 4,
                "events": [
                    {
                        "eventid": 9999,
                        "eventdivision": "12U",
                        "eventclassification": "Major",
                        "countteams": 4,
                        "eventstartdate": "2026-03-01",
                        "eventenddate": "2026-03-02",
                    }
                ],
            }
        ]
    )
    tournament = tournaments[0]
    client = MagicMock()
    with patch(
        "baseball_aggregator.collectors.perfect_game.fetch_tournament_teams",
        side_effect=httpx.HTTPError("connection refused"),
    ):
        pg_enrich(tournament, client, target_age="12U")

    assert tournament.division_teams.get("12U MAJOR") == []


def test_usssa_enrich_populates_division_teams():
    """Verify usssa_enrich calls fetch_seeding_report_teams and stores results."""
    from baseball_aggregator.collectors.usssa import parse_division_results
    from baseball_aggregator.models import Tournament

    tournament = Tournament(
        source="usssa",
        source_id="99999",
        name="Test USSSA",
        detail_url="",
        location="",
        age_divisions=["12U", "12U OPEN"],
    )
    divisions = parse_division_results(
        [{"class": "12Op", "teamEntered": 8, "teamApproved": 8, "ID": "div-001", "eventFormat": "Pool to 3GG"}]
    )
    tournament.division_team_counts = divisions["counts"]
    tournament.division_confirmed_counts = divisions["approved"]
    tournament.division_details = divisions["details"]
    tournament.division_teams = {d: [] for d in divisions["counts"]}

    fake_teams = [{"team_name": "Panthers Baseball", "record": "0-3-0", "division": "12U OPEN"}]
    client = MagicMock()
    with patch(
        "baseball_aggregator.collectors.usssa.fetch_seeding_report_teams",
        return_value=fake_teams,
    ) as mock_fetch:
        usssa_enrich(tournament, client, target_age="12U")
        mock_fetch.assert_called_once_with(client, "div-001", "12U OPEN")

    assert tournament.division_teams["12U OPEN"] == fake_teams


# ---------------------------------------------------------------------------
# parse_usssa_age_division tests
# ---------------------------------------------------------------------------

def test_parse_usssa_age_division_8u_class_a():
    name = "(2026) Easley Baseball Club Schmitt 8U (8 & Under A) | Madison, Alabama"
    assert parse_usssa_age_division(name) == "8 & Under A"


def test_parse_usssa_age_division_10u():
    name = "(2026) Some Team 10U (10 & Under) | Huntsville, AL"
    assert parse_usssa_age_division(name) == "10 & Under"


def test_parse_usssa_age_division_12u_style():
    name = "(2026) Hawks Baseball (12U) | Madison, AL"
    assert parse_usssa_age_division(name) == "12U"


def test_parse_usssa_age_division_no_match():
    assert parse_usssa_age_division("Team Name Without Age") == ""


def test_parse_usssa_age_division_empty():
    assert parse_usssa_age_division("") == ""


# ---------------------------------------------------------------------------
# USSSA ties fallback test
# ---------------------------------------------------------------------------

def test_usssa_ties_fallback_when_overall_ties_null():
    """When OverallTies is null/missing, fall back to in-class Ties field."""
    payload = {
        "seedingReport": {
            "tournaments": [
                {
                    "teamname": "Test Team",
                    "OverallWins": 7,
                    "OverallLoses": 5,
                    "OverallTies": None,  # null from API
                    "Wins": 3,
                    "Loses": 2,
                    "Ties": 1,           # in-class fallback
                    "teamid": "123",
                }
            ]
        }
    }
    teams = parse_usssa_teams(payload, "8U OPEN")
    assert len(teams) == 1
    assert teams[0]["overall_record"] == "7-5-1"


def test_usssa_ties_fallback_when_overall_ties_present():
    """When OverallTies is present (non-null), use it directly."""
    payload = {
        "seedingReport": {
            "tournaments": [
                {
                    "teamname": "Test Team",
                    "OverallWins": 7,
                    "OverallLoses": 5,
                    "OverallTies": 2,
                    "Wins": 3,
                    "Loses": 2,
                    "Ties": 1,
                    "teamid": "456",
                }
            ]
        }
    }
    teams = parse_usssa_teams(payload, "8U OPEN")
    assert len(teams) == 1
    assert teams[0]["overall_record"] == "7-5-2"
