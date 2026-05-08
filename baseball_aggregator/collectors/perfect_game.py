from __future__ import annotations

import re
import json
from datetime import date
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from baseball_aggregator.collectors.common import clean_text, parse_date_range
from baseball_aggregator.models import Tournament

SOURCE = "perfect_game"
BASE_URL = "https://search.perfectgame.org/"
DETAIL_BASE_URL = "https://www.perfectgame.org"
SEARCH_ACTION_ID = "dad9504030d7a1e855028212db463c6a70b140af"
HUNTSVILLE_CITY = "Huntsville"
HUNTSVILLE_STATE = "AL"
HUNTSVILLE_LAT = 34.6981
HUNTSVILLE_LNG = -86.6412
PAGE_SIZE = 50
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
    radius_miles: int = 200,
    city: str = HUNTSVILLE_CITY,
    state: str = HUNTSVILLE_STATE,
    lat: float = HUNTSVILLE_LAT,
    lng: float = HUNTSVILLE_LNG,
    target_age: str | None = None,
    enrich_team_lists: bool = True,
    client: httpx.Client | None = None,
) -> list[Tournament]:
    own_client = client is None
    if own_client:
        client = httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True)

    try:
        start_date, end_date = season_window()
        search_url = search_page_url(city, state, lat, lng, radius_miles, start_date, end_date)
        client.get(search_url)

        all_groups = []
        page = 1
        while True:
            payload = search_payload(
                radius_miles=radius_miles,
                lat=lat,
                lng=lng,
                start_date=start_date,
                end_date=end_date,
                page=page,
            )
            data = post_search_action(client, search_url, payload)
            all_groups.extend(data.get("results") or [])
            if not data.get("hasNextPage"):
                break
            page += 1

        tournaments = parse_api_results(all_groups)
        if enrich_team_lists:
            for tournament in tournaments:
                enrich_with_team_lists(tournament, client, target_age)
        return tournaments
    finally:
        if own_client:
            client.close()


def search_page_url(
    city: str,
    state: str,
    lat: float,
    lng: float,
    radius_miles: int,
    start_date: date,
    end_date: date,
) -> str:
    request = httpx.Request(
        "GET",
        BASE_URL,
        params={
            "city": city,
            "lat": str(lat),
            "lng": str(lng),
            "state": state,
            "radius": str(radius_miles),
            "sportType": "Baseball",
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        },
    )
    return str(request.url)


def search_payload(
    radius_miles: int,
    lat: float,
    lng: float,
    start_date: date,
    end_date: date,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "search_query": "",
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "sportType": "Baseball",
        "classification": [],
        "circuit": [],
        "division": [],
        "director": [],
        "state": [],
        "eventType": [],
        "ballpark": "",
        "teamName": "",
        "eventDkscoringplanned": "notset",
        "pgbaflagcolor": "",
        "eventPrimaryBallparkCity": "",
        "minTeams": None,
        "maxTeams": None,
        "minTotalTeams": None,
        "maxTotalTeams": None,
        "search_latitude": lat,
        "search_longitude": lng,
        "search_radius_miles": radius_miles,
        "sort": "date_asc",
        "semantic": "elastic",
        "page": page,
        "pageSize": PAGE_SIZE,
    }


def post_search_action(client: httpx.Client, referer: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        referer,
        headers={
            **HEADERS,
            "Accept": "text/x-component",
            "Content-Type": "application/json",
            "Next-Action": SEARCH_ACTION_ID,
            "Origin": BASE_URL.rstrip("/"),
            "Referer": referer,
        },
        content=json.dumps([payload]),
    )
    response.raise_for_status()
    return parse_action_response(response.text)


def parse_action_response(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if not re.match(r"^[0-9a-f]+:", line):
            continue
        _, value = line.split(":", 1)
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "results" in payload:
            return payload
    return {"results": []}


def parse_api_results(groups: list[dict[str, Any]]) -> list[Tournament]:
    return [parse_api_group(group) for group in groups if group.get("eventgroupid")]


def parse_api_group(group: dict[str, Any]) -> Tournament:
    source_id = str(group.get("eventgroupid") or "")
    events = group.get("events") or []
    first_event = events[0] if events else {}
    name = clean_text(group.get("eventschedulename") or group.get("eventgroupname") or first_event.get("eventname") or "")
    location = clean_text(
        f"{group.get('eventprimaryballparkcity') or first_event.get('eventprimaryballparkcity') or ''}, "
        f"{group.get('eventprimaryballparkstate') or first_event.get('eventprimaryballparkstate') or ''}"
    ).strip(", ")
    start_date = parse_iso_date(first_event.get("eventstartdate")) or parse_epoch_ms(group.get("startDate"))
    end_date = parse_iso_date(first_event.get("eventenddate")) or parse_epoch_ms(group.get("endDate"))
    division_data = parse_division_counts(events)

    return Tournament(
        source=SOURCE,
        source_id=source_id,
        name=name,
        detail_url=f"{DETAIL_BASE_URL}/Schedule/GroupedEvents.aspx?gid={source_id}" if source_id else "",
        location=location,
        director=clean_text(first_event.get("director") or "") or None,
        start_date=start_date,
        end_date=end_date,
        age_divisions=division_data["age_divisions"],
        registered_teams=parse_int(group.get("total_teams")) or sum(division_data["counts"].values()),
        division_team_counts=division_data["counts"],
        division_confirmed_counts=division_data["confirmed"],
        division_details=division_data["details"],
        division_teams={division: [] for division in division_data["counts"]},
        team_count_scope="division" if division_data["counts"] else "event",
        stature=clean_text(first_event.get("eventtype") or group.get("circuit") or "") or None,
        format=clean_text(group.get("circuit") or "") or None,
        logo_url=group.get("eventgrouplogo"),
    )


def fetch_tournament_teams(client: httpx.Client, event_id: str, division: str) -> list[dict[str, Any]]:
    response = client.get(
        f"{DETAIL_BASE_URL}/Events/TournamentTeams.aspx",
        params={"event": event_id},
        headers=HEADERS,
    )
    response.raise_for_status()
    return parse_tournament_teams(response.text, division)


def enrich_with_team_lists(
    tournament: Tournament,
    client: httpx.Client,
    target_age: str | None = None,
) -> Tournament:
    target = target_age.upper() if target_age else ""
    for division, details in tournament.division_details.items():
        if target and not division.upper().startswith(f"{target} "):
            continue
        if tournament.division_team_counts.get(division, 0) <= 0:
            continue
        event_id = details.get("event_id")
        if not event_id:
            continue
        try:
            teams = fetch_tournament_teams(client, str(event_id), division)
        except (httpx.HTTPError, RuntimeError, ValueError):
            teams = []
        if not teams:
            continue
        tournament.division_teams[division] = teams
        age_match = re.match(r"^(\d{1,2}U)\b", division, re.IGNORECASE)
        if age_match:
            age_key = age_match.group(1).upper()
            tournament.division_teams.setdefault(age_key, []).extend(teams)
    return tournament


def parse_tournament_teams(html: str, division: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    table = next(
        (
            table
            for table in soup.find_all("table")
            if table.select('a[href*="Tournaments/Teams/Default.aspx?team="]')
        ),
        None,
    )
    if table is None:
        return []

    teams = []
    for row in table.find_all("tr"):
        link = row.select_one('a[href*="Tournaments/Teams/Default.aspx?team="]')
        if link is None:
            continue
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        team_name = clean_text(link.get_text(" ", strip=True))
        team_text = cells[2] if len(cells) > 2 else ""
        record_match = re.search(r"\(([^)]+?)\s+in\s+\d{4}\)", team_text, re.IGNORECASE)
        teams.append(
            {
                "number": len(teams) + 1,
                "team_name": team_name,
                "confirmed": False,
                "division": division,
                "city_state": clean_text(cells[4] if len(cells) > 4 else ""),
                "record": clean_text(record_match.group(1) if record_match else ""),
                "team_class": clean_text(cells[3] if len(cells) > 3 else ""),
                "national_rank": clean_text(cells[0] if cells else ""),
                "manager_name": clean_text(cells[5] if len(cells) > 5 else ""),
                "detail_url": urljoin(DETAIL_BASE_URL, link.get("href", "")),
            }
        )
    return teams


def parse_division_counts(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    confirmed: dict[str, int] = {}
    details: dict[str, dict[str, Any]] = {}
    age_divisions: list[str] = []

    for event in events:
        division = normalize_division(event.get("eventdivision"), event.get("eventclassification"))
        if not division:
            continue
        teams = parse_int(event.get("countteams")) or 0
        counts[division] = counts.get(division, 0) + teams
        confirmed[division] = confirmed.get(division, 0)
        details[division] = {
            "event_id": event.get("eventid"),
            "raw_division": clean_text(event.get("eventdivision") or ""),
            "raw_classification": clean_text(event.get("eventclassification") or ""),
            "event_format": clean_text(event.get("eventtype") or ""),
            "location": clean_text(
                f"{event.get('eventprimaryballparkcity') or ''}, {event.get('eventprimaryballparkstate') or ''}"
            ).strip(", "),
            "ballpark": clean_text(event.get("eventprimaryballparkname") or ""),
            "entry_fee": parse_int(event.get("eventfee")),
            "detail_url": (
                f"{DETAIL_BASE_URL}/Events/Default.aspx?event={event.get('eventid')}"
                if event.get("eventid")
                else ""
            ),
        }
        if division not in age_divisions:
            age_divisions.append(division)

        age = normalize_age(event.get("eventdivision"))
        if age and age != division:
            counts[age] = counts.get(age, 0) + teams
            confirmed[age] = confirmed.get(age, 0)
            if age not in age_divisions:
                age_divisions.append(age)

    return {
        "counts": counts,
        "confirmed": confirmed,
        "details": details,
        "age_divisions": sorted(age_divisions, key=division_sort_key),
    }


def parse_event_list(html: str) -> list[Tournament]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("[data-pg-event], [data-pg-event-id], [data-event-id]")
    return [parse_event_card(card) for card in cards]


def parse_event_card(card) -> Tournament:
    source_id = (
        card.get("data-id", "")
        or card.get("data-pg-event-id", "")
        or card.get("data-event-id", "")
    )
    name_el = card.select_one(".pg-event-name")
    location_el = card.select_one(".pg-event-location")
    date_el = card.select_one(".pg-event-date")
    teams_el = card.select_one(".pg-event-teams")
    ages_el = card.select_one(".pg-event-ages")
    stature_el = card.select_one(".pg-event-stature")
    link_el = card.select_one("a[href]")

    start_date, end_date = parse_date_range(clean_text(date_el.get_text()) if date_el else "")
    registered_teams = None
    if teams_el:
        match = re.search(r"\d+", teams_el.get_text())
        registered_teams = int(match.group(0)) if match else None

    ages = []
    if ages_el:
        ages = [item.strip() for item in re.split(r"[,|\u00b7\u2022]+", ages_el.get_text()) if item.strip()]

    return Tournament(
        source=SOURCE,
        source_id=source_id,
        name=clean_text(name_el.get_text()) if name_el else "",
        detail_url=urljoin(BASE_URL, link_el.get("href", "")) if link_el else "",
        location=clean_text(location_el.get_text()) if location_el else "",
        start_date=start_date,
        end_date=end_date,
        age_divisions=ages,
        registered_teams=registered_teams,
        team_count_scope="event",
        stature=clean_text(stature_el.get_text()) if stature_el else None,
    )


def season_window(today: date | None = None) -> tuple[date, date]:
    current = today or date.today()
    if current.month >= 10:
        start_year = current.year
    else:
        start_year = current.year - 1
    return (date(start_year, 12, 29), date(start_year + 2, 1, 3))


def normalize_division(age_value: Any, class_value: Any = None) -> str:
    age = normalize_age(age_value)
    if not age:
        return ""
    classification = clean_text(class_value or "").upper()
    return f"{age} {classification}".strip() if classification else age


def normalize_age(value: Any) -> str:
    match = re.search(r"\d{1,2}", str(value or ""))
    return f"{int(match.group(0))}U" if match else ""


def parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_epoch_ms(value: Any) -> date | None:
    try:
        timestamp = int(value) / 1000
    except (TypeError, ValueError):
        return None
    return date.fromtimestamp(timestamp)


def parse_int(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def division_sort_key(value: str) -> tuple[int, str]:
    match = re.match(r"^(\d{1,2})U\b(.*)$", value, re.IGNORECASE)
    if not match:
        return (99, value)
    return (int(match.group(1)), match.group(2).strip())
