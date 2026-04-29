from __future__ import annotations

from baseball_aggregator.models import Tournament

SOURCE = "grand_slam"


def fetch_tournaments(*args, **kwargs) -> list[Tournament]:
    # Public Grand Slam collection needs live-site reconnaissance before enabling.
    return []


def parse_event_list(html: str) -> list[Tournament]:
    # Placeholder parser so Grand Slam can be wired through the app while the
    # source-specific public page shape is still being mapped.
    return []
