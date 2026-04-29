from __future__ import annotations

import re
from datetime import date

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_date_range(text: str, today: date | None = None) -> tuple[date | None, date | None]:
    if not text:
        return None, None
    today = today or date.today()
    text = text.strip()

    match = re.match(r"([A-Za-z]+)\s+(\d+)\s*-\s*([A-Za-z]+)\s+(\d+)", text)
    if match:
        start = make_date(match.group(1), int(match.group(2)), today)
        end = make_date(match.group(3), int(match.group(4)), today)
        if start and end and end < start:
            end = end.replace(year=end.year + 1)
        return start, end

    match = re.match(r"([A-Za-z]+)\s+(\d+)\s*-\s*(\d+)", text)
    if match:
        month = match.group(1)
        return make_date(month, int(match.group(2)), today), make_date(month, int(match.group(3)), today)

    match = re.match(r"([A-Za-z]+)\s+(\d+)", text)
    if match:
        start = make_date(match.group(1), int(match.group(2)), today)
        return start, start

    return None, None


def make_date(month_str: str, day: int, today: date) -> date | None:
    month = MONTHS.get(month_str.lower()[:3])
    if not month:
        return None
    try:
        value = date(today.year, month, day)
    except ValueError:
        return None
    if (today - value).days > 30:
        value = date(today.year + 1, month, day)
    return value
