from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from baseball_aggregator.models import Tournament
from baseball_aggregator.storage import connect, init_db, upsert_tournaments


DEFAULT_ARTIFACT_DIR = ROOT / ".tmp" / "ui-demos"
DEFAULT_DATA_DIR = ROOT / ".tmp" / "ui-demo-data"


def main() -> int:
    args = parse_args()
    artifact_dir = args.artifact_dir.resolve()
    screenshot_dir = artifact_dir / "screenshots"
    video_dir = artifact_dir / "videos"
    data_dir = args.data_dir.resolve()

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)
    prepare_data_dir(data_dir, preserve=args.preserve_data)
    seed_demo_data(data_dir)

    env = os.environ.copy()
    env.update(
        {
            "STAFF_TOOL_DATA_DIR": str(data_dir),
            "STAFF_TOOL_ENABLE_HOSTED_JOBS": "false",
        }
    )
    env.pop("STAFF_TOOL_HOSTED", None)
    env.pop("RAILWAY_ENVIRONMENT", None)
    env.pop("STAFF_TOOL_PASSWORD", None)

    server = None
    base_url = args.base_url.rstrip("/")
    if not args.skip_server:
        server = start_server(args.port, env)
        base_url = f"http://127.0.0.1:{args.port}"

    try:
        wait_for_app(base_url)
        capture_artifacts(base_url, screenshot_dir, video_dir)
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()

    print(f"UI demo artifacts written to {artifact_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture Playwright screenshots and videos for UI review.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--skip-server", action="store_true", help="Use an already-running app at --base-url.")
    parser.add_argument("--preserve-data", action="store_true", help="Keep the existing demo SQLite database.")
    return parser.parse_args()


def prepare_data_dir(data_dir: Path, preserve: bool) -> None:
    if preserve:
        data_dir.mkdir(parents=True, exist_ok=True)
        return
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)


def seed_demo_data(data_dir: Path) -> None:
    os.environ["STAFF_TOOL_DATA_DIR"] = str(data_dir)
    with connect() as conn:
        init_db(conn)
        upsert_tournaments(
            conn,
            [
                Tournament(
                    source="ncs",
                    source_id="demo-ncs-1",
                    name="Rocket City Spring Ring",
                    detail_url="https://example.com/tournaments/rocket-city",
                    location="Huntsville, AL",
                    start_date=date(2026, 5, 16),
                    end_date=date(2026, 5, 17),
                    age_divisions=["8U", "8U Open", "8U AA"],
                    registered_teams=9,
                    division_team_counts={"8U Open": 5, "8U AA": 4},
                    division_confirmed_counts={"8U Open": 4, "8U AA": 3},
                    division_details={
                        "8U Open": {"min_games": "3", "event_format": "Pool to bracket"},
                        "8U AA": {"min_games": "3", "event_format": "Saturday pool"},
                    },
                    division_teams={
                        "8U Open": [
                            {"number": 1, "team_name": "Huntsville Hawks", "confirmed": True, "city_state": "Huntsville, AL", "record": "8-2", "team_class": "Open"},
                            {"number": 2, "team_name": "Madison Thunder", "confirmed": True, "city_state": "Madison, AL", "record": "6-3", "team_class": "Open"},
                            {"number": 3, "team_name": "Athens Heat", "confirmed": True, "city_state": "Athens, AL", "record": "5-4", "team_class": "Open"},
                        ],
                    },
                    team_count_scope="division",
                    stature="Qualifier",
                    format="3GG",
                    distance_miles=8,
                ),
                Tournament(
                    source="usssa",
                    source_id="demo-usssa-1",
                    name="North Alabama Classic",
                    detail_url="https://example.com/tournaments/north-alabama",
                    location="Decatur, AL",
                    start_date=date(2026, 6, 6),
                    end_date=date(2026, 6, 7),
                    age_divisions=["8U", "8U AA"],
                    registered_teams=3,
                    division_team_counts={"8U AA": 3},
                    division_confirmed_counts={"8U AA": 2},
                    team_count_scope="division",
                    stature="State Qualifier",
                    format="2 pool / single elimination",
                    distance_miles=28,
                ),
            ],
        )


def start_server(port: int, env: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "baseball_aggregator.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )


def wait_for_app(base_url: str) -> None:
    deadline = time.time() + 30
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/settings", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
        time.sleep(0.5)
    raise RuntimeError(f"App did not become ready at {base_url}: {last_error}")


def capture_artifacts(base_url: str, screenshot_dir: Path, video_dir: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: python -m pip install -r requirements-dev.txt"
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        desktop = browser.new_context(
            viewport={"width": 1440, "height": 980},
            record_video_dir=str(video_dir),
        )
        page = desktop.new_page()
        page.goto(base_url)
        page.wait_for_selector("#tournamentRows tr")
        page.screenshot(path=screenshot_dir / "staff-tool-desktop-dark.png", full_page=True)

        page.get_by_title("Switch between light and dark theme").click()
        page.screenshot(path=screenshot_dir / "staff-tool-desktop-light.png", full_page=True)

        page.locator(".teams-toggle").first.click()
        page.wait_for_selector(".team-details-row:not([hidden])")
        page.screenshot(path=screenshot_dir / "staff-tool-team-details.png", full_page=True)
        desktop.close()

        mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            record_video_dir=str(video_dir),
        )
        mobile_page = mobile.new_page()
        mobile_page.goto(base_url)
        mobile_page.wait_for_selector("#tournamentRows tr")
        mobile_page.screenshot(path=screenshot_dir / "staff-tool-mobile.png", full_page=True)
        mobile.close()
        browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
