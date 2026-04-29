from __future__ import annotations

from baseball_aggregator.collectors import ncs, perfect_game, usssa

COLLECTORS = {
    "ncs": ncs,
    "usssa": usssa,
    "perfect_game": perfect_game,
}


def list_collectors() -> list[str]:
    return list(COLLECTORS.keys())


def get_collector(source: str):
    return COLLECTORS[source]
