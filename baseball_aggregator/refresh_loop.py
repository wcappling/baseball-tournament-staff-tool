from __future__ import annotations

import time

from baseball_aggregator.services import refresh_sources
from baseball_aggregator.storage import connect, get_settings, init_db


def main() -> None:
    with connect() as conn:
        init_db(conn)
        settings = get_settings(conn)
    cadence_seconds = int(settings["refresh_cadence_hours"]) * 60 * 60
    print(f"Starting refresh loop every {settings['refresh_cadence_hours']} hours.")
    while True:
        print(refresh_sources())
        time.sleep(cadence_seconds)


if __name__ == "__main__":
    main()
