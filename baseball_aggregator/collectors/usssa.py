from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from baseball_aggregator.collectors.common import clean_text, parse_date_range
from baseball_aggregator.models import Tournament

SOURCE = "usssa"
BASE_URL = "https://usssa.com"
SEARCH_PAGE = f"{BASE_URL}/baseball/eventSearch/"
API_URL = f"{BASE_URL}/api/"
HUNTSVILLE_ZIP = "35801"
SEASON_ID_2026 = "30"
API_TOKEN_FALLBACK = "eventSearchV4!!!Get"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_tournaments(
    radius_miles: int = 200,
    zip_code: str = HUNTSVILLE_ZIP,
    season_id: str = SEASON_ID_2026,
    target_age: str | None = None,
    polite_delay_sec: float = 0.1,
    enrich_divisions: bool = True,
    enrich_team_lists: bool = True,
    client: httpx.Client | None = None,
) -> list[Tournament]:
    own_client = client is None
    if own_client:
        client = httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True)

    try:
        token = fetch_api_token(client, zip_code, radius_miles, season_id)
        payload = search_payload(zip_code, radius_miles, season_id, token)
        data = api_post(client, "eventSearchSimpleV11", payload)
        tournaments = parse_api_results(data)
        if enrich_divisions:
            for tournament in tournaments:
                enrich_with_divisions(tournament, client, token)
                if enrich_team_lists:
                    enrich_with_seeding_reports(tournament, client, target_age)
                if polite_delay_sec > 0:
                    time.sleep(polite_delay_sec)
        return tournaments
    finally:
        if own_client:
            client.close()


def fetch_api_token(
    client: httpx.Client,
    zip_code: str = HUNTSVILLE_ZIP,
    radius_miles: int = 200,
    season_id: str = SEASON_ID_2026,
) -> str:
    params = {
        "sportID": "11",
        "seasonID": season_id,
        "class": "0",
        "region": "0",
        "zip": zip_code,
        "mile": str(radius_miles),
        "period": "0",
    }
    try:
        response = client.get(SEARCH_PAGE, params=params)
        response.raise_for_status()
    except httpx.HTTPError:
        return API_TOKEN_FALLBACK

    match = re.search(r"apiAccessToken\s*=\s*['\"]([^'\"]+)['\"]", response.text)
    return match.group(1) if match else API_TOKEN_FALLBACK


def search_payload(zip_code: str, radius_miles: int, season_id: str, token: str) -> dict[str, str]:
    return {
        "sportID": "11",
        "seasonID": season_id,
        "age": "",
        "classID": "0",
        "stateID": "",
        "regionID": "0",
        "zip": zip_code,
        "mile": str(radius_miles),
        "statureID": "",
        "startDate": date.today().strftime("%m/%d/%Y"),
        "endDate": "",
        "director": "",
        "parkID": "",
        "token": token,
    }


def api_post(
    client: httpx.Client,
    action: str,
    data: dict[str, str],
    referer: str = SEARCH_PAGE,
) -> Any:
    response = client.post(
        API_URL,
        params={"action": action},
        data=data,
        headers={"Referer": referer, **HEADERS},
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("Error"):
        raise RuntimeError(payload.get("Message") or f"USSSA API error for {action}")
    return payload


def enrich_with_divisions(tournament: Tournament, client: httpx.Client, token: str) -> Tournament:
    data = api_post(client, "eventSearch-Divisions", {"eventID": tournament.source_id, "token": token})
    divisions = parse_division_results(data)
    if not divisions:
        return tournament

    tournament.division_team_counts = divisions["counts"]
    tournament.division_confirmed_counts = divisions["approved"]
    tournament.division_details = divisions["details"]
    tournament.division_teams = {division: [] for division in divisions["counts"]}
    tournament.team_count_scope = "division"
    tournament.age_divisions = divisions["age_divisions"]
    if divisions["event_format"]:
        tournament.format = divisions["event_format"]
    return tournament


def enrich_with_seeding_reports(
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

        division_id = details.get("division_id")
        if not division_id:
            continue

        try:
            teams = fetch_seeding_report_teams(client, str(division_id), division)
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


def fetch_seeding_report_teams(client: httpx.Client, division_id: str, division: str) -> list[dict[str, Any]]:
    payload = api_post(
        client,
        "selpV2",
        {
            "eventID": "",
            "divisionID": division_id,
            "tabName": "seedingReport",
        },
        referer=f"{BASE_URL}/baseball/event_seedingReport/?eventID=&divisionID={division_id}",
    )
    return parse_seeding_report_teams(payload, division)


def parse_seeding_report_teams(payload: Any, division: str) -> list[dict[str, Any]]:
    report = payload.get("seedingReport", {}) if isinstance(payload, dict) else {}
    if report.get("notAvailable"):
        return []
    teams = report.get("tournaments") or []
    parsed = []
    for index, team in enumerate(teams, start=1):
        team_id = str(team.get("teamid") or "")
        city_state = " - ".join(
            value
            for value in [clean_text(team.get("TeamState") or ""), clean_text(team.get("teamcity") or "")]
            if value
        )
        in_class_record = format_record(team.get("Wins"), team.get("Loses"), team.get("Ties"))
        overall_record = format_record(team.get("OverallWins"), team.get("OverallLoses"), team.get("OverallTies"))
        parsed.append(
            {
                "number": index,
                "team_name": clean_text(team.get("teamname") or ""),
                "confirmed": True,
                "division": division,
                "city_state": city_state,
                "record": overall_record,
                "in_class_record": in_class_record,
                "overall_record": overall_record,
                "team_class": clean_text(team.get("TeamClass") or ""),
                "manager_name": clean_text(team.get("ManagerName") or ""),
                "points": team.get("points"),
                "rating": team.get("Rating"),
                "detail_url": f"{BASE_URL}/baseball/teamHome/?teamID={team_id}" if team_id else "",
            }
        )
    return parsed


def parse_event_list(html: str) -> list[Tournament]:
    text = html.strip()
    if text.startswith("{") or text.startswith("["):
        return parse_api_results(json.loads(text))

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("[data-tournament]")
    return [parse_event_card(card) for card in cards]


def parse_api_results(payload: Any) -> list[Tournament]:
    events = payload.get("results", []) if isinstance(payload, dict) else payload
    return [parse_api_event(event) for event in events or []]


def parse_api_event(event: dict[str, Any]) -> Tournament:
    source_id = str(event.get("ID") or "")
    start_date = parse_usssa_date(event.get("start_date"))
    end_date = parse_usssa_date(event.get("end_date"))
    location = clean_text(f"{event.get('eventLocation') or event.get('city') or ''}, {event.get('stateABR') or ''}").strip(", ")
    registered_teams = parse_int(event.get("teamCount"))
    detail_url = f"{BASE_URL}/baseball/event_home/?eventID={source_id}" if source_id else ""
    age_divisions = parse_event_divisions_all(event.get("eventDivisionsAll") or event.get("eventDivisions") or "")

    return Tournament(
        source=SOURCE,
        source_id=source_id,
        name=clean_text(event.get("event_name") or ""),
        detail_url=detail_url,
        location=location,
        director=clean_text(event.get("eventDirector") or "") or None,
        start_date=start_date,
        end_date=end_date,
        age_divisions=age_divisions,
        registered_teams=registered_teams,
        team_count_scope="event",
        stature=clean_text(event.get("stature") or "") or None,
        format=clean_text(event.get("eventType") or "") or None,
        logo_url=event.get("eventLogo"),
    )


def parse_division_results(payload: Any) -> dict[str, Any]:
    counts: dict[str, int] = {}
    approved: dict[str, int] = {}
    details: dict[str, dict[str, Any]] = {}
    age_divisions: list[str] = []
    event_format = ""

    divisions = payload if isinstance(payload, list) else []
    for item in divisions:
        division = normalize_division(item.get("class") or "")
        if not division:
            continue
        registered = parse_int(item.get("teamEntered")) or 0
        confirmed = parse_int(item.get("teamApproved")) or 0
        counts[division] = registered
        approved[division] = confirmed
        details[division] = {
            "division_id": item.get("ID"),
            "raw_division": clean_text(item.get("class") or ""),
            "max_entries": parse_int(item.get("maxTeams")),
            "pending_entries": parse_int(item.get("teamPending")) or 0,
            "min_games": parse_int(item.get("minimum_number_games")),
            "entry_fee": parse_int(item.get("entryFee")),
            "gate_fee": parse_int(item.get("gateFee")),
            "other_fee": parse_int(item.get("otherFee")),
            "location": clean_text(item.get("city") or ""),
            "event_format": clean_text(item.get("eventFormat") or ""),
            "stature": clean_text(item.get("stature") or ""),
            "sold_out": bool(item.get("soldOut")),
            "deadline_passed": bool(item.get("deadlinePassed")),
        }
        age_divisions.append(division)
        if not event_format:
            event_format = clean_text(item.get("eventFormat") or "")

        age_match = re.match(r"^(\d{1,2}U)\b", division, re.IGNORECASE)
        if age_match:
            age_key = age_match.group(1).upper()
            counts[age_key] = counts.get(age_key, 0) + registered
            approved[age_key] = approved.get(age_key, 0) + confirmed
            if age_key not in age_divisions:
                age_divisions.append(age_key)

    return {
        "counts": counts,
        "approved": approved,
        "details": details,
        "age_divisions": age_divisions,
        "event_format": event_format,
    }


def parse_event_card(card) -> Tournament:
    source_id = card.get("data-id", "")
    name_el = card.select_one(".event-name")
    location_el = card.select_one(".event-location")
    date_el = card.select_one(".event-date")
    teams_el = card.select_one(".event-teams")
    ages_el = card.select_one(".event-ages")
    stature_el = card.select_one(".event-stature")
    link_el = card.select_one("a[href]")

    start_date, end_date = parse_date_range(clean_text(date_el.get_text()) if date_el else "")
    registered_teams = None
    if teams_el:
        registered_teams = parse_int(teams_el.get_text())

    ages = []
    if ages_el:
        ages = [item.strip() for item in re.split(r"[,|\u00b7\u2022]+", ages_el.get_text()) if item.strip()]

    return Tournament(
        source=SOURCE,
        source_id=source_id,
        name=clean_text(name_el.get_text()) if name_el else "",
        detail_url=link_el.get("href", "") if link_el else "",
        location=clean_text(location_el.get_text()) if location_el else "",
        start_date=start_date,
        end_date=end_date,
        age_divisions=ages,
        registered_teams=registered_teams,
        team_count_scope="event",
        stature=clean_text(stature_el.get_text()) if stature_el else None,
    )


def parse_event_divisions_all(value: str) -> list[str]:
    divisions: list[str] = []
    for age_chunk in str(value or "").split("#"):
        if "%" not in age_chunk:
            division = normalize_division(age_chunk)
            if division:
                divisions.append(division)
            continue
        age, classes = age_chunk.split("%", 1)
        age = normalize_age(age)
        if age and age not in divisions:
            divisions.append(age)
        for class_name in classes.split("|"):
            division = normalize_division(f"{age}{class_name}")
            if division and division not in divisions:
                divisions.append(division)
    return divisions


def normalize_division(value: str) -> str:
    raw = clean_text(str(value or "")).replace(" ", "")
    if not raw:
        return ""

    match = re.match(r"^(\d{1,2})(?:U)?([A-Za-z].*)?$", raw, re.IGNORECASE)
    if not match:
        return clean_text(value).upper()

    age = f"{int(match.group(1))}U"
    suffix = (match.group(2) or "").strip()
    if not suffix:
        return age

    suffix = re.sub(r"^Op(en)?", "OPEN", suffix, flags=re.IGNORECASE)
    suffix = re.sub(r"^Maj(or)?", "MAJOR", suffix, flags=re.IGNORECASE)
    suffix = re.sub(r"^Rec", "REC", suffix, flags=re.IGNORECASE)
    suffix = suffix.upper()
    for token in ("MAJOR", "OPEN", "REC", "AAA", "AA", "A"):
        if suffix.startswith(token):
            if suffix != token:
                suffix = f"{token} {suffix[len(token):]}"
            break
    return f"{age} {suffix}".strip()


def normalize_age(value: str) -> str:
    match = re.search(r"\d{1,2}", str(value or ""))
    return f"{int(match.group(0))}U" if match else ""


def parse_usssa_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def format_record(wins: Any, losses: Any, ties: Any = None) -> str:
    if wins is None and losses is None:
        return ""
    w = parse_int(wins) or 0
    l = parse_int(losses) or 0
    t = parse_int(ties) or 0
    return f"{w}-{l}-{t}"
