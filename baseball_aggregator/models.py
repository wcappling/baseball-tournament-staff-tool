from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any


DEFAULT_SETTINGS = {
    "home_zip": "35801",
    "home_label": "Huntsville, AL",
    "radius_miles": 200,
    "target_age_division": "8U",
    "team_count_threshold": 4,
    "refresh_cadence_hours": 6,
    "enabled_sources": ["ncs", "usssa", "perfect_game"],
}


@dataclass
class Tournament:
    source: str
    source_id: str
    name: str
    detail_url: str
    location: str = ""
    director: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    age_divisions: list[str] = field(default_factory=list)
    registered_teams: int | None = None
    division_team_counts: dict[str, int] = field(default_factory=dict)
    division_confirmed_counts: dict[str, int] = field(default_factory=dict)
    division_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    division_teams: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    team_count_scope: str = "event"
    stature: str | None = None
    format: str | None = None
    tags: list[str] = field(default_factory=list)
    logo_url: str | None = None
    distance_miles: float | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def target_count(self, target_age: str | None) -> int | None:
        if target_age and target_age in self.division_team_counts:
            return self.division_team_counts[target_age]
        return self.registered_teams

    def count_scope_for(self, target_age: str | None) -> str:
        if target_age and target_age in self.division_team_counts:
            return "division"
        return self.team_count_scope or "event"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["start_date"] = self.start_date.isoformat() if self.start_date else None
        data["end_date"] = self.end_date.isoformat() if self.end_date else None
        data["fetched_at"] = self.fetched_at.isoformat()
        return data


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)
