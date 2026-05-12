from __future__ import annotations

import sqlite3
from pathlib import Path

from baseball_aggregator import storage, team_admin


def test_team_admin_create_updates_team_login_and_settings(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "baseball_staff_tool.sqlite3"

    exit_code = team_admin.main(
        [
            "upsert",
            "--db-path",
            str(db_path),
            "--slug",
            "8u-hawks",
            "--display-name",
            "8U Hawks",
            "--password",
            "eight-pass",
            "--age",
            "8U",
            "--radius",
            "100",
            "--home-label",
            "Huntsville 8U",
            "--enabled-source",
            "ncs",
            "--enabled-source",
            "usssa",
        ]
    )

    assert exit_code == 0
    assert "8u-hawks" in capsys.readouterr().out
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        team = storage.verify_team_password(conn, "8u-hawks", "eight-pass")
        assert team is not None
        settings = storage.get_team_settings(conn, team["id"])
        assert settings["target_age_division"] == "8U"
        assert settings["radius_miles"] == 100
        assert settings["home_label"] == "Huntsville 8U"
        assert settings["enabled_sources"] == ["ncs", "usssa"]

    exit_code = team_admin.main(
        [
            "upsert",
            "--db-path",
            str(db_path),
            "--slug",
            "8u-hawks",
            "--display-name",
            "8U Hawks Updated",
            "--password",
            "new-eight-pass",
            "--age",
            "9U",
            "--radius",
            "150",
        ]
    )

    assert exit_code == 0
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        assert storage.verify_team_password(conn, "8u-hawks", "eight-pass") is None
        team = storage.verify_team_password(conn, "8u-hawks", "new-eight-pass")
        assert team is not None
        assert team["display_name"] == "8U Hawks Updated"
        settings = storage.get_team_settings(conn, team["id"])
        assert settings["target_age_division"] == "9U"
        assert settings["radius_miles"] == 150


def test_team_admin_list_does_not_print_password_hash(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "baseball_staff_tool.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        storage.init_db(conn)
        storage.create_team(conn, slug="9u-hawks", display_name="9U Hawks", password="nine-pass")

    exit_code = team_admin.main(["list", "--db-path", str(db_path)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "9u-hawks" in output
    assert "9U Hawks" in output
    assert "pbkdf2" not in output
    assert "nine-pass" not in output
