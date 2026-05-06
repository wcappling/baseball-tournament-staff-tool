from __future__ import annotations

import math
import re

HUNTSVILLE = (34.7304, -86.5861)

CITY_COORDS = {
    ("Albertville", "AL"): (34.2676, -86.2089),
    ("Athens", "AL"): (34.8029, -86.9717),
    ("Birmingham", "AL"): (33.5186, -86.8104),
    ("Cullman", "AL"): (34.1748, -86.8436),
    ("Decatur", "AL"): (34.6059, -86.9833),
    ("Florence", "AL"): (34.7998, -87.6773),
    ("Fort Payne", "AL"): (34.4443, -85.7197),
    ("Gadsden", "AL"): (34.0143, -86.0066),
    ("Guntersville", "AL"): (34.3581, -86.2947),
    ("Haleyville", "AL"): (34.2265, -87.6214),
    ("Hoover", "AL"): (33.4054, -86.8114),
    ("Huntsville", "AL"): HUNTSVILLE,
    ("Madison", "AL"): (34.6993, -86.7483),
    ("Montgomery", "AL"): (32.3792, -86.3077),
    ("Oxford", "AL"): (33.6143, -85.8349),
    ("Rainsville", "AL"): (34.4943, -85.8477),
    ("Russellville", "AL"): (34.5079, -87.7286),
    ("Scottsboro", "AL"): (34.6723, -86.0341),
    ("Tuscaloosa", "AL"): (33.2098, -87.5692),
    ("Chattanooga", "TN"): (35.0456, -85.3097),
    ("Columbia", "TN"): (35.6151, -87.0353),
    ("Franklin", "TN"): (35.9251, -86.8689),
    ("Germantown", "TN"): (35.0868, -89.8101),
    ("Jackson", "TN"): (35.6145, -88.8139),
    ("Murfreesboro", "TN"): (35.8456, -86.3903),
    ("Nashville", "TN"): (36.1627, -86.7816),
    ("Smyrna", "TN"): (35.9828, -86.5186),
    ("Atlanta", "GA"): (33.7490, -84.3880),
    ("Cartersville", "GA"): (34.1651, -84.7999),
    ("Dalton", "GA"): (34.7698, -84.9702),
    ("Marietta", "GA"): (33.9526, -84.5499),
    ("Rome", "GA"): (34.2570, -85.1647),
    ("Horn Lake", "MS"): (34.9554, -90.0348),
    ("Southaven", "MS"): (34.9890, -90.0126),
    ("Tupelo", "MS"): (34.2576, -88.7034),
    ("Benton", "KY"): (36.8573, -88.3503),
    ("Murray", "KY"): (36.6103, -88.3148),
}


def estimate_distance_miles(location: str | None) -> float | None:
    candidates = _location_candidates(location)
    distances: list[float] = []
    for city, state in candidates:
        coords = CITY_COORDS.get((city, state))
        if coords:
            distances.append(_haversine(HUNTSVILLE, coords))
    return round(min(distances), 1) if distances else None


def _location_candidates(location: str | None) -> list[tuple[str, str]]:
    if not location:
        return []
    text = re.sub(r"\s+", " ", location).strip()
    state_match = re.search(r",\s*([A-Z]{2})\b", text)
    if not state_match:
        return []

    state = state_match.group(1)
    city_part = text[: state_match.start()]
    parts = re.split(r"\s*/\s*|\s*-\s*|\s*,\s*|\s*&\s*|\s+\band\b\s+", city_part, flags=re.IGNORECASE)
    return [(_title_city(part), state) for part in parts if part.strip()]


def _title_city(city: str) -> str:
    return " ".join(word.capitalize() for word in city.strip().split())


def _haversine(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lon1 = start
    lat2, lon2 = end
    radius_miles = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_miles * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
