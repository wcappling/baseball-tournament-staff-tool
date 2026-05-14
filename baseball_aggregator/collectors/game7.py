from __future__ import annotations

import re
import time

import httpx
from bs4 import BeautifulSoup, Tag

from baseball_aggregator.collectors.common import clean_text, parse_date_range
from baseball_aggregator.models import Tournament

SOURCE = "game7"
BASE_URL = "https://www.game7baseball.com/baseball/Events"
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
    enrich_whos_coming: bool = True,
    whos_coming_delay_sec: float = 0.25,
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
                    if enrich_whos_coming:
                        enrich_with_whos_coming(tournament, client)
                        if whos_coming_delay_sec > 0:
                            time.sleep(whos_coming_delay_sec)
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


def enrich_with_whos_coming(tournament: Tournament, client: httpx.Client) -> Tournament:
    url = whos_coming_url(tournament)
    if not url:
        return tournament
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError:
        return tournament

    division_counts, division_teams = parse_whos_coming(response.text)
    if not division_counts:
        return tournament

    tournament.division_team_counts = division_counts
    tournament.division_teams = division_teams
    tournament.team_count_scope = "division"
    for division in division_counts:
        if division not in tournament.age_divisions:
            tournament.age_divisions.append(division)
    return tournament


def whos_coming_url(tournament: Tournament) -> str:
    if "/Events/Details/" not in tournament.detail_url:
        return ""
    return tournament.detail_url.replace("/Events/Details/", "/Events/WhosComing/", 1)


def parse_whos_coming_counts(html: str) -> dict[str, int]:
    counts, _teams = parse_whos_coming(html)
    return counts


def parse_whos_coming(html: str) -> tuple[dict[str, int], dict[str, list[dict[str, str]]]]:
    soup = BeautifulSoup(html, "html.parser")
    counts: dict[str, int] = {}
    teams_by_division: dict[str, list[dict[str, str]]] = {}

    for panel in soup.select("#whosComingContainer .panel"):
        division_el = panel.select_one(".panel-heading .division")
        registered_el = panel.select_one(".panel-heading .registered")
        division = clean_text(division_el.get_text()) if division_el else ""
        registered_text = clean_text(registered_el.get_text(" ")) if registered_el else ""
        if not division:
            continue

        teams = _parse_whos_coming_team_rows(panel)
        match = re.search(r"(\d+)\s+Teams?\s+Registered", registered_text, re.IGNORECASE)
        if teams:
            count = len(teams)
        elif match:
            count = int(match.group(1))
        else:
            continue

        counts[division] = count
        teams_by_division[division] = teams

        age_match = re.match(r"^(\d{1,2}U)\b", division, re.IGNORECASE)
        if age_match:
            age_key = age_match.group(1).upper()
            if age_key != division.upper():
                counts[age_key] = counts.get(age_key, 0) + count
                teams_by_division.setdefault(age_key, []).extend(teams)

    return counts, teams_by_division


def _parse_whos_coming_team_rows(panel: Tag) -> list[dict[str, str]]:
    teams: list[dict[str, str]] = []
    headers = [
        clean_text(header.get_text()).lower().replace("-", "_")
        for header in panel.select("table thead th")
    ]
    for row in panel.select("table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        number = _cell_text(cells, headers, "#", 0)
        team_index = _column_index(headers, "team name", 1)
        team_cell = cells[team_index] if team_index < len(cells) else cells[1]
        team_link = team_cell.select_one("a[href]")
        team_name = clean_text(team_link.get_text() if team_link else team_cell.get_text())
        if team_name.lower() == "open" and team_link is None:
            continue

        detail_url = ""
        if team_link:
            href = team_link.get("href", "")
            detail_url = f"https://www.game7baseball.com{href}" if href.startswith("/") else href

        confirmed_index = _column_index(headers, "confirmed", -1)
        confirmed = False
        if 0 <= confirmed_index < len(cells):
            confirmed_cell = cells[confirmed_index]
            confirmed = bool(confirmed_cell.select_one(".fa-check, .glyphicon-ok")) or bool(
                clean_text(confirmed_cell.get_text())
            )

        division = _cell_text(cells, headers, "division", 2)
        city_state = _cell_text(cells, headers, "city/state", 3)
        record = _cell_text(cells, headers, "w_l_t", len(cells) - 1)
        if team_name:
            teams.append(
                {
                    "number": number,
                    "team_name": team_name,
                    "confirmed": confirmed,
                    "division": division,
                    "city_state": city_state,
                    "record": record,
                    "detail_url": detail_url,
                }
            )
    return teams


def _column_index(headers: list[str], header: str, default: int) -> int:
    normalized = header.lower().replace("-", "_")
    try:
        return headers.index(normalized)
    except ValueError:
        return default


def _cell_text(cells: list[Tag], headers: list[str], header: str, default_index: int) -> str:
    index = _column_index(headers, header, default_index)
    if 0 <= index < len(cells):
        return clean_text(cells[index].get_text())
    return ""


def parse_event_list(html: str) -> list[Tournament]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.media-list.media-list-events > div.media")
    return [_parse_event_card(card) for card in cards]


def _parse_event_card(card: Tag) -> Tournament:
    body = card.select_one(".media-body")
    if body is None:
        return Tournament(source=SOURCE, source_id="", name="", detail_url="")

    name_link = body.select_one(".h4 a")
    href = name_link.get("href", "") if name_link else ""
    detail_url = f"https://www.game7baseball.com{href}" if href.startswith("/") else href
    id_match = re.search(r"/Details/(\d+)/", href)

    header_h6 = body.select_one(".h6")
    location = ""
    director = None
    if header_h6:
        for span in header_h6.find_all("span", recursive=False):
            classes = span.get("class") or []
            if "director" in classes:
                director = clean_text(span.get_text()).lstrip("|").strip() or None
            elif not location:
                location = clean_text(span.get_text())

    h4_elements = body.select(".h4")
    date_text = clean_text(h4_elements[1].get_text()) if len(h4_elements) > 1 else ""
    start_date, end_date = parse_date_range(date_text)

    teams_el = body.select_one(".h5 strong")
    registered_teams = None
    if teams_el:
        try:
            registered_teams = int(clean_text(teams_el.get_text()))
        except ValueError:
            registered_teams = None

    h6_elements = body.select(".h6")
    age_divisions: list[str] = []
    if len(h6_elements) > 1:
        ages_text = h6_elements[-1].get_text(" ", strip=True)
        age_divisions = [age.strip() for age in re.split(r"[·•]", ages_text) if age.strip()]

    stature_el = card.select_one(".media-top .stature")
    format_el = body.select_one("p.small")
    logo_el = card.select_one(".media-thumbnail img")

    return Tournament(
        source=SOURCE,
        source_id=id_match.group(1) if id_match else "",
        name=clean_text(name_link.get_text()) if name_link else "",
        detail_url=detail_url,
        location=location,
        director=director,
        start_date=start_date,
        end_date=end_date,
        age_divisions=age_divisions,
        registered_teams=registered_teams,
        team_count_scope="event",
        stature=clean_text(stature_el.get_text()) if stature_el else None,
        format=clean_text(format_el.get_text()) if format_el else None,
        tags=[clean_text(label.get_text()) for label in body.select(".tags .label")],
        logo_url=logo_el.get("src") if logo_el else None,
    )
