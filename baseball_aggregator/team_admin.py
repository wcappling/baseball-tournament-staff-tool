from __future__ import annotations

import argparse
from pathlib import Path

from baseball_aggregator import storage


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "upsert":
        return upsert_team(args)
    if args.command == "list":
        return list_configured_teams(args)
    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, update, and inspect shared team logins.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upsert = subparsers.add_parser("upsert", help="Create or update a team login.")
    add_db_path(upsert)
    upsert.add_argument("--slug", required=True, help="Stable login slug, for example 8u-hawks.")
    upsert.add_argument("--display-name", required=True, help="Human-readable team name.")
    upsert.add_argument("--password", required=True, help="Shared team password. Rerun to rotate.")
    upsert.add_argument("--age", dest="target_age_division", help="Default target age, for example 8U.")
    upsert.add_argument("--radius", dest="radius_miles", type=int, help="Default radius in miles.")
    upsert.add_argument("--home-label", help="Display label for the team's home base.")
    upsert.add_argument("--home-zip", help="Home ZIP for future collector/distance support.")
    upsert.add_argument("--threshold", dest="team_count_threshold", type=int, help="Default team-count threshold.")
    upsert.add_argument(
        "--enabled-source",
        action="append",
        dest="enabled_sources",
        help="Enabled source slug. Repeat for multiple sources.",
    )

    list_parser = subparsers.add_parser("list", help="List configured teams without secrets.")
    add_db_path(list_parser)
    return parser


def add_db_path(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db-path", type=Path, help="SQLite database path. Defaults to STAFF_TOOL_DATA_DIR/db.")


def upsert_team(args: argparse.Namespace) -> int:
    settings = {
        key: value
        for key, value in {
            "target_age_division": args.target_age_division,
            "radius_miles": args.radius_miles,
            "home_label": args.home_label,
            "home_zip": args.home_zip,
            "team_count_threshold": args.team_count_threshold,
            "enabled_sources": args.enabled_sources,
        }.items()
        if value is not None
    }
    with storage.connect(args.db_path) as conn:
        team = storage.create_team(
            conn,
            slug=args.slug,
            display_name=args.display_name,
            password=args.password,
            settings=settings,
        )
        team_settings = storage.get_team_settings(conn, team["id"])
    print(
        f"team {team['slug']} saved: {team['display_name']} "
        f"({team_settings['target_age_division']}, {team_settings['radius_miles']} mi)"
    )
    return 0


def list_configured_teams(args: argparse.Namespace) -> int:
    with storage.connect(args.db_path) as conn:
        rows = storage.list_teams(conn)
    for row in rows:
        active = "active" if row["active"] else "inactive"
        print(f"{row['slug']}\t{row['display_name']}\t{active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
