from __future__ import annotations

import re
import time

import httpx
from bs4 import BeautifulSoup, Tag

from baseball_aggregator.collectors.common import clean_text, parse_date_range
from baseball_aggregator.models import Tournament

SOURCE = "grand_slam"
BASE_URL = "https://www.grandslamtournaments.com/baseball/Events"
HUNTSVILLE_ZIP = "35801"
HUNTSVILLE_LAT = 34.736449
HUNTSVILLE_LNG = -86.550165
DEFAULT_RADIUS_MILES = 200
RESULTS_PER_PAGE = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_tournaments(
    radius_miles: int = DEFAULT_RADIUS_MILES,
    max_pages: int = 20,
    polite_delay_sec: float = 1.0,
    target_age: str | None = None,
    client: httpx.Client | None = None,
) -> list[Tournament]:
    own_client = client is None
    if own_client:
        client = httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True)

    seen_ids: set[str] = set()
    results: list[Tournament] = []

    try:
        for page in range(1, max_pages + 1):
            params = {
                "page": page,
                "zip": HUNTSVILLE_ZIP,
                "radius": radius_miles,
                "ll": f"{HUNTSVILLE_LAT},{HUNTSVILLE_LNG}",
            }
            response = client.get(BASE_URL, params=params)
            response.raise_for_status()
            page_tournaments = parse_event_list(response.text)

            new_count = 0
            for tournament in page_tournaments:
                if tournament.source_id and tournament.source_id not in seen_ids:
                    seen_ids.add(tournament.source_id)
                    results.append(tournament)
                    new_count += 1

            if not page_tournaments or new_count == 0 or len(page_tournaments) < RESULTS_PER_PAGE:
                break
            if polite_delay_sec > 0 and page < max_pages:
                time.sleep(polite_delay_sec)
    finally:
        if own_client:
            client.close()

    return results


def parse_event_list(html: str) -> list[Tournament]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.media-list.media-list-events > div.media[data-eventid]")
    return [_parse_event_card(card) for card in cards]


def _parse_event_card(card: Tag) -> Tournament:
    event_id = str(card.get("data-eventid", ""))

    body = card.select_one(".media-body")

    name_el = body.select_one(".h3 strong") if body else None
    name = clean_text(name_el.get_text()) if name_el else ""

    date_el = body.select_one(".h4") if body else None
    date_text = clean_text(date_el.get_text()) if date_el else ""
    start_date, end_date = parse_date_range(date_text)

    location = ""
    registered_teams = None
    if body:
        for h5 in body.select(".h5"):
            strong = h5.select_one("strong")
            if not strong:
                continue
            text = clean_text(strong.get_text())
            if re.search(r"Teams?\s+Registered", text, re.IGNORECASE):
                match = re.search(r"(\d+)", text)
                if match:
                    registered_teams = int(match.group(1))
            elif not location:
                location = text

    age_divisions: list[str] = []
    for btn in card.select(".media-right .ages button.badge[data-agenumber]"):
        age_num = btn.get("data-agenumber", "")
        if age_num:
            age_divisions.append(f"{age_num}U")

    detail_link = card.select_one(".ctas a[href*='/Events/Details/']")
    href = detail_link.get("href", "") if detail_link else ""
    detail_url = f"https://www.grandslamtournaments.com{href}" if href.startswith("/") else href

    logo_url = None
    thumbnail = card.select_one(".media-thumbnail")
    if thumbnail:
        style = thumbnail.get("style", "")
        match = re.search(r"url\(([^)]+)\)", style)
        if match:
            logo_url = match.group(1).strip("'\"")

    return Tournament(
        source=SOURCE,
        source_id=event_id,
        name=name,
        detail_url=detail_url,
        location=location,
        start_date=start_date,
        end_date=end_date,
        age_divisions=age_divisions,
        registered_teams=registered_teams,
        team_count_scope="event",
        logo_url=logo_url,
    )
