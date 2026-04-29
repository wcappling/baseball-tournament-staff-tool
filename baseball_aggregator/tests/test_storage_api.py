import sqlite3

from fastapi.testclient import TestClient

from baseball_aggregator.app import app
from baseball_aggregator.models import Tournament
from baseball_aggregator.storage import init_db, list_divisions, search_tournaments, upsert_tournaments


def test_storage_threshold_and_change_detection():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="1",
                    name="Test Tournament",
                    detail_url="https://example.com",
                    location="Madison, AL",
                    age_divisions=["12U"],
                    registered_teams=3,
                    division_team_counts={"12U": 3, "12U OPEN": 3},
                    division_teams={
                        "12U": [
                            {"team_name": "Team A", "confirmed": True, "division": "12U OPEN", "city_state": "Madison, AL", "record": "3-1-0"},
                            {"team_name": "Team B", "confirmed": False, "division": "12U OPEN", "city_state": "Decatur, AL", "record": "2-2-0"},
                            {"team_name": "Team C", "confirmed": False, "division": "12U OPEN", "city_state": "Athens, AL", "record": "1-3-0"},
                        ],
                        "12U OPEN": [
                            {"team_name": "Team A", "confirmed": True, "division": "12U OPEN", "city_state": "Madison, AL", "record": "3-1-0"},
                            {"team_name": "Team B", "confirmed": False, "division": "12U OPEN", "city_state": "Decatur, AL", "record": "2-2-0"},
                            {"team_name": "Team C", "confirmed": False, "division": "12U OPEN", "city_state": "Athens, AL", "record": "1-3-0"},
                        ],
                    },
                    team_count_scope="division",
                )
            ],
        )
        rows = search_tournaments(conn, {"age": "12U", "threshold": 4})
        assert rows[0]["meets_team_threshold"] is False
        assert len(rows[0]["selected_age_teams"]) == 3
        assert rows[0]["selected_age_confirmed_count"] == 1

        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="1",
                    name="Test Tournament",
                    detail_url="https://example.com",
                    location="Madison, AL",
                    age_divisions=["12U"],
                    registered_teams=5,
                    division_team_counts={"12U": 5, "12U OPEN": 5},
                    division_teams={
                        "12U": [
                            {"team_name": "Team A", "confirmed": True, "division": "12U OPEN", "city_state": "Madison, AL", "record": "3-1-0"},
                            {"team_name": "Team B", "confirmed": False, "division": "12U OPEN", "city_state": "Decatur, AL", "record": "2-2-0"},
                            {"team_name": "Team C", "confirmed": False, "division": "12U OPEN", "city_state": "Athens, AL", "record": "1-3-0"},
                            {"team_name": "Team D", "confirmed": True, "division": "12U OPEN", "city_state": "Huntsville, AL", "record": "4-0-0"},
                            {"team_name": "Team E", "confirmed": True, "division": "12U OPEN", "city_state": "Cullman, AL", "record": "5-1-0"},
                        ],
                        "12U OPEN": [
                            {"team_name": "Team A", "confirmed": True, "division": "12U OPEN", "city_state": "Madison, AL", "record": "3-1-0"},
                            {"team_name": "Team B", "confirmed": False, "division": "12U OPEN", "city_state": "Decatur, AL", "record": "2-2-0"},
                            {"team_name": "Team C", "confirmed": False, "division": "12U OPEN", "city_state": "Athens, AL", "record": "1-3-0"},
                            {"team_name": "Team D", "confirmed": True, "division": "12U OPEN", "city_state": "Huntsville, AL", "record": "4-0-0"},
                            {"team_name": "Team E", "confirmed": True, "division": "12U OPEN", "city_state": "Cullman, AL", "record": "5-1-0"},
                        ],
                    },
                    team_count_scope="division",
                )
            ],
        )
        rows = search_tournaments(conn, {"age": "12U", "threshold": 4})
        assert rows[0]["meets_team_threshold"] is True
        assert rows[0]["target_team_count"] == 5
        assert rows[0]["selected_age_divisions"] == [
            {"division": "12U OPEN", "registered": 5, "confirmed": 3, "details": {}}
        ]
        assert len(rows[0]["selected_age_teams"]) == 5
        assert rows[0]["selected_age_confirmed_count"] == 3
        assert rows[0]["count_warning"] is False


def test_selected_age_returns_each_matching_division_count():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="12270",
                    name="NCS - Mother's Day Classic",
                    detail_url="https://example.com",
                    location="Fort Payne / Rainsville, AL",
                    age_divisions=["8U", "8U D3 CP", "8U OPEN CP"],
                    registered_teams=67,
                    division_team_counts={"8U": 4, "8U D3 CP": 4, "8U OPEN CP": 0},
                    division_teams={
                        "8U": [
                            {"team_name": "Team A", "confirmed": False, "division": "8U D3 CP"},
                            {"team_name": "Team B", "confirmed": False, "division": "8U D3 CP"},
                            {"team_name": "Team C", "confirmed": False, "division": "8U D3 CP"},
                            {"team_name": "Team D", "confirmed": False, "division": "8U D3 CP"},
                        ],
                        "8U D3 CP": [
                            {"team_name": "Team A", "confirmed": False, "division": "8U D3 CP"},
                            {"team_name": "Team B", "confirmed": False, "division": "8U D3 CP"},
                            {"team_name": "Team C", "confirmed": False, "division": "8U D3 CP"},
                            {"team_name": "Team D", "confirmed": False, "division": "8U D3 CP"},
                        ],
                        "8U OPEN CP": [],
                    },
                    team_count_scope="division",
                )
            ],
        )
        rows = search_tournaments(conn, {"age": "8U", "threshold": 4})
        assert rows[0]["target_team_count"] == 4
        assert rows[0]["selected_age_confirmed_count"] == 0
        assert rows[0]["selected_age_divisions"] == [
            {"division": "8U D3 CP", "registered": 4, "confirmed": 0, "details": {}},
            {"division": "8U OPEN CP", "registered": 0, "confirmed": 0, "details": {}},
        ]


def test_selected_age_uses_source_confirmed_counts_without_team_rows():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="usssa",
                    source_id="407473",
                    name="Bat To The Future",
                    detail_url="https://usssa.com/baseball/event_home/?eventID=407473",
                    location="OXFORD, MS",
                    age_divisions=["12U", "12U OPEN", "12U AA"],
                    registered_teams=91,
                    division_team_counts={"12U": 32, "12U OPEN": 12, "12U AA": 20},
                    division_confirmed_counts={"12U": 28, "12U OPEN": 10, "12U AA": 18},
                    division_details={
                        "12U OPEN": {"max_entries": 12, "pending_entries": 2, "min_games": 3, "event_format": "Pool to 3GG"},
                        "12U AA": {"max_entries": 24, "pending_entries": 2, "min_games": 3, "event_format": "Pool to 3GG"},
                    },
                    team_count_scope="division",
                )
            ],
        )
        rows = search_tournaments(conn, {"age": "12U", "threshold": 4})
        assert rows[0]["selected_age_divisions"][0]["division"] == "12U AA"
        assert rows[0]["selected_age_divisions"][0]["registered"] == 20
        assert rows[0]["selected_age_divisions"][0]["confirmed"] == 18
        assert rows[0]["selected_age_divisions"][0]["details"]["max_entries"] == 24
        assert rows[0]["selected_age_divisions"][1]["division"] == "12U OPEN"
        assert rows[0]["selected_age_divisions"][1]["details"]["min_games"] == 3
        assert rows[0]["selected_age_confirmed_count"] == 28

        rows = search_tournaments(conn, {"age": "12U", "division": "12U AA", "threshold": 4})
        assert rows[0]["target_team_count"] == 20
        assert rows[0]["selected_age_divisions"] == [
            {
                "division": "12U AA",
                "registered": 20,
                "confirmed": 18,
                "details": {"max_entries": 24, "pending_entries": 2, "min_games": 3, "event_format": "Pool to 3GG"},
            }
        ]

        rows = search_tournaments(conn, {"age": "12U", "division": ["12U AA", "12U OPEN"], "threshold": 4})
        assert rows[0]["target_team_count"] == 32
        assert [item["division"] for item in rows[0]["selected_age_divisions"]] == ["12U AA", "12U OPEN"]


def test_division_options_are_discovered_from_saved_tournaments():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="usssa",
                    source_id="divisions",
                    name="Division Event",
                    detail_url="https://example.com",
                    age_divisions=["12U", "12U OPEN", "12U AA", "14U AA"],
                    division_team_counts={"12U": 5, "12U OPEN": 2, "12U AA": 3, "14U AA": 4},
                )
            ],
        )
        assert list_divisions(conn, age="12U") == ["12U AA", "12U OPEN"]
        assert list_divisions(conn, age="14U") == ["14U AA"]


def test_api_settings_and_empty_tournament_list():
    client = TestClient(app)
    settings = client.get("/api/settings").json()
    assert settings["home_zip"] == "35801"
    response = client.get("/api/tournaments")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_age_filter_does_not_match_substrings():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="8",
                    name="Eight U Event",
                    detail_url="https://example.com/8",
                    age_divisions=["8U", "8U OPEN"],
                    registered_teams=4,
                ),
                Tournament(
                    source="ncs",
                    source_id="18",
                    name="Eighteen U Event",
                    detail_url="https://example.com/18",
                    age_divisions=["18U", "18U OPEN"],
                    registered_teams=9,
                ),
            ],
        )
        rows = search_tournaments(conn, {"age": "8U", "threshold": 4})
        assert [row["name"] for row in rows] == ["Eight U Event"]


def test_distance_filter_uses_radius_without_changing_base_dataset():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        init_db(conn)
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="near",
                    name="Near Event",
                    detail_url="https://example.com/near",
                    location="Madison, AL",
                    age_divisions=["12U"],
                    registered_teams=4,
                ),
                Tournament(
                    source="ncs",
                    source_id="far",
                    name="Far Event",
                    detail_url="https://example.com/far",
                    location="Birmingham, AL",
                    age_divisions=["12U"],
                    registered_teams=6,
                ),
                Tournament(
                    source="ncs",
                    source_id="unknown",
                    name="Unknown Event",
                    detail_url="https://example.com/unknown",
                    location="Mystery, AL",
                    age_divisions=["12U"],
                    registered_teams=8,
                ),
            ],
        )
        rows_25 = search_tournaments(conn, {"age": "12U", "radius_miles": 25})
        assert [row["name"] for row in rows_25] == ["Near Event"]

        rows_200 = search_tournaments(conn, {"age": "12U", "radius_miles": 200})
        assert {row["name"] for row in rows_200} == {"Near Event", "Far Event", "Unknown Event"}
