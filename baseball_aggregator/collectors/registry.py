from __future__ import annotations

from baseball_aggregator.collectors import game7, grand_slam, ncs, perfect_game, usssa

COLLECTORS = {
    "ncs": ncs,
    "usssa": usssa,
    "perfect_game": perfect_game,
    "grand_slam": grand_slam,
    "game7": game7,
}


def list_collectors() -> list[str]:
    return list(COLLECTORS.keys())


def get_collector(source: str):
    return COLLECTORS[source]
