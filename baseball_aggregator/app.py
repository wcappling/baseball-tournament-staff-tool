from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from baseball_aggregator.auth import PasswordAuthMiddleware, handle_login, handle_logout, login_page
from baseball_aggregator.config import get_backup_dir, hosted_jobs_enabled, require_hosted_config
from baseball_aggregator.maintenance import create_sqlite_backup, prune_backups
from baseball_aggregator import services
from baseball_aggregator.storage import (
    connect,
    get_changes,
    get_settings,
    init_db,
    latest_refresh_runs,
    list_divisions,
    search_tournaments,
    update_settings,
    upsert_shortlist,
)

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    require_hosted_config()
    with connect() as conn:
        init_db(conn)
    refresh_task = None
    backup_task = None
    if hosted_jobs_enabled():
        refresh_task = asyncio.create_task(_refresh_loop())
        backup_task = asyncio.create_task(_backup_loop())
    yield
    for task in (refresh_task, backup_task):
        if task:
            task.cancel()
    for task in (refresh_task, backup_task):
        if task:
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Baseball Tournament Staff Tool", lifespan=lifespan)
app.add_middleware(PasswordAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/login")
def login():
    return login_page()


@app.post("/login")
async def post_login(request: Request):
    return await handle_login(request)


@app.post("/logout")
def post_logout():
    return handle_logout()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/settings")
def api_get_settings():
    with connect() as conn:
        return get_settings(conn)


@app.put("/api/settings")
def api_update_settings(payload: dict[str, Any]):
    with connect() as conn:
        return update_settings(conn, payload)


@app.get("/api/tournaments")
def api_tournaments(
    source: str | None = None,
    age: str | None = None,
    division: list[str] | None = Query(default=None),
    threshold: int | None = None,
    radius_miles: int | None = None,
    start_after: str | None = None,
    q: str | None = None,
):
    with connect() as conn:
        return search_tournaments(
            conn,
            {
                "source": source,
                "age": age,
                "division": division,
                "threshold": threshold,
                "radius_miles": radius_miles,
                "start_after": start_after,
                "q": q,
            },
        )


@app.get("/api/divisions")
def api_divisions(source: str | None = None, age: str | None = None):
    with connect() as conn:
        return list_divisions(conn, age=age, source=source)


@app.post("/api/refresh")
def api_refresh(payload: dict[str, Any] | None = None):
    sources = payload.get("sources") if payload else None
    return services.refresh_sources(sources=sources)


@app.post("/api/tournaments/{tournament_id}/teams")
def api_tournament_teams(
    tournament_id: int,
    age: str,
    division: list[str] | None = Query(default=None),
):
    return services.hydrate_tournament_teams(tournament_id, age, division)


@app.get("/api/changes")
def api_changes(limit: int = 50):
    with connect() as conn:
        return get_changes(conn, limit=limit)


@app.get("/api/refresh-runs")
def api_refresh_runs():
    with connect() as conn:
        return latest_refresh_runs(conn)


@app.put("/api/tournaments/{tournament_id}/shortlist")
def api_shortlist(tournament_id: int, payload: dict[str, Any]):
    with connect() as conn:
        return upsert_shortlist(conn, tournament_id, payload)


async def _refresh_loop() -> None:
    while True:
        with connect() as conn:
            settings = get_settings(conn)
        cadence_seconds = max(1, int(settings["refresh_cadence_hours"])) * 60 * 60
        await asyncio.sleep(cadence_seconds)
        await asyncio.to_thread(services.refresh_sources)


async def _backup_loop() -> None:
    while True:
        now = datetime.now(UTC)
        tomorrow = (now + timedelta(days=1)).date()
        next_run = datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC)
        await asyncio.sleep((next_run - now).total_seconds())
        await asyncio.to_thread(create_sqlite_backup)
        await asyncio.to_thread(prune_backups, get_backup_dir(), 7)
