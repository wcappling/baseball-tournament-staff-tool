from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from baseball_aggregator.auth import (
    COOKIE_NAME,
    PasswordAuthMiddleware,
    get_web_team_id,
    handle_login,
    handle_logout,
    login_page,
)
from baseball_aggregator.config import get_backup_dir, hosted_jobs_enabled, require_hosted_config
from baseball_aggregator.maintenance import create_sqlite_backup, prune_backups
from baseball_aggregator import services, stats
from baseball_aggregator.storage import (
    connect,
    get_changes,
    get_session_for_token,
    get_settings,
    get_team_settings,
    init_db,
    latest_refresh_runs,
    list_divisions,
    revoke_team_session,
    search_tournaments,
    create_team_session,
    update_settings,
    update_team_settings,
    upsert_shortlist,
    verify_team_password,
)

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


class NativeLoginRequest(BaseModel):
    team_slug: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TeamSettingsUpdate(BaseModel):
    home_zip: str | None = None
    home_label: str | None = None
    radius_miles: int | None = Field(default=None, ge=1)
    target_age_division: str | None = None
    team_count_threshold: int | None = Field(default=None, ge=1)
    refresh_cadence_hours: int | None = Field(default=None, ge=1)
    enabled_sources: list[str] | None = None
    brand_primary: str | None = None
    brand_secondary: str | None = None
    brand_accent: str | None = None
    logo_url: str | None = None

    def clean_payload(self) -> dict[str, Any]:
        return {key: value for key, value in self.model_dump().items() if value is not None}


class ShortlistUpdateRequest(BaseModel):
    status: str = "Watch"
    priority: int = Field(default=3, ge=1)
    notes: str = ""


def api_error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


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


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/v1/") and isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", "http_error"))
        message = str(exc.detail.get("message", "Request failed."))
        return api_error(code, message, exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.get("/login")
def login():
    return login_page()


@app.post("/login")
async def post_login(request: Request):
    return await handle_login(request)


@app.post("/logout")
def post_logout():
    return handle_logout()


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "authentication_required", "message": "Bearer token required."})
    return authorization.split(" ", 1)[1].strip()


def _native_session(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = _bearer_token(authorization)
    with connect() as conn:
        session = get_session_for_token(conn, token)
    if session is None:
        raise HTTPException(status_code=401, detail={"code": "invalid_session", "message": "Session is invalid or expired."})
    session["token"] = token
    return session


def _team_payload(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": session["team_id"],
        "slug": session["team_slug"],
        "display_name": session["team_display_name"],
    }


def _web_team_id(request: Request) -> str:
    return get_web_team_id(request.cookies.get(COOKIE_NAME)) or "default"


@app.post("/api/v1/login")
def api_v1_login(payload: NativeLoginRequest):
    with connect() as conn:
        team = verify_team_password(conn, payload.team_slug, payload.password)
        if team is None:
            return api_error("invalid_credentials", "Invalid team login.", 401)
        session = create_team_session(conn, team["id"])
    return {
        "team": {"id": team["id"], "slug": team["slug"], "display_name": team["display_name"]},
        "session": session,
    }


@app.get("/api/v1/me")
def api_v1_me(session: dict[str, Any] = Depends(_native_session)):
    return {
        "team": _team_payload(session),
        "session": {"expires_at": session["expires_at"]},
    }


@app.post("/api/v1/logout")
def api_v1_logout(session: dict[str, Any] = Depends(_native_session)):
    with connect() as conn:
        revoke_team_session(conn, session["token"])
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/settings")
def api_get_settings(request: Request):
    with connect() as conn:
        team_id = _web_team_id(request)
        settings = get_team_settings(conn, team_id)
        team = conn.execute("SELECT slug, display_name FROM teams WHERE id = ?", (team_id,)).fetchone()
        if team:
            settings["team_slug"] = team["slug"]
            settings["team_display_name"] = team["display_name"]
        return settings


@app.put("/api/settings")
def api_update_settings(payload: dict[str, Any], request: Request):
    with connect() as conn:
        return update_team_settings(conn, _web_team_id(request), payload)


@app.get("/api/v1/settings")
def api_v1_get_settings(session: dict[str, Any] = Depends(_native_session)):
    with connect() as conn:
        settings = get_team_settings(conn, session["team_id"])
    return {"team": _team_payload(session), "settings": settings}


@app.put("/api/v1/settings")
def api_v1_update_settings(
    payload: TeamSettingsUpdate,
    session: dict[str, Any] = Depends(_native_session),
):
    with connect() as conn:
        settings = update_team_settings(conn, session["team_id"], payload.clean_payload())
    return {"team": _team_payload(session), "settings": settings}


@app.get("/api/tournaments")
def api_tournaments(
    request: Request,
    source: str | None = None,
    age: str | None = None,
    division: list[str] | None = Query(default=None),
    threshold: int | None = None,
    radius_miles: int | None = None,
    start_on_or_after: str | None = None,
    end_on_or_before: str | None = None,
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
                "start_on_or_after": start_on_or_after,
                "end_on_or_before": end_on_or_before,
                "q": q,
            },
            team_id=_web_team_id(request),
        )


@app.get("/api/v1/tournaments")
def api_v1_tournaments(
    source: str | None = None,
    age: str | None = None,
    division: list[str] | None = Query(default=None),
    threshold: int | None = None,
    radius_miles: int | None = None,
    start_on_or_after: str | None = None,
    end_on_or_before: str | None = None,
    q: str | None = None,
    session: dict[str, Any] = Depends(_native_session),
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
                "start_on_or_after": start_on_or_after,
                "end_on_or_before": end_on_or_before,
                "q": q,
            },
            team_id=session["team_id"],
        )


@app.get("/api/v1/tournaments/{tournament_id}")
def api_v1_tournament_detail(
    tournament_id: int,
    age: str | None = None,
    division: list[str] | None = Query(default=None),
    session: dict[str, Any] = Depends(_native_session),
):
    with connect() as conn:
        settings = get_team_settings(conn, session["team_id"])
        row = services.get_tournament_detail(
            tournament_id,
            age or settings["target_age_division"],
            int(settings["team_count_threshold"]),
            division,
            team_id=session["team_id"],
        )
    if row is None:
        return api_error("not_found", "Tournament not found.", 404)
    return row


@app.get("/api/divisions")
def api_divisions(source: str | None = None, age: str | None = None):
    with connect() as conn:
        return list_divisions(conn, age=age, source=source)


@app.get("/api/v1/divisions")
def api_v1_divisions(
    source: str | None = None,
    age: str | None = None,
    session: dict[str, Any] = Depends(_native_session),
):
    with connect() as conn:
        settings = get_team_settings(conn, session["team_id"])
        return list_divisions(conn, age=age or settings["target_age_division"], source=source)


@app.post("/api/refresh")
def api_refresh(payload: dict[str, Any] | None = None):
    sources = payload.get("sources") if payload else None
    return services.refresh_sources(sources=sources)


@app.post("/api/v1/refresh")
def api_v1_refresh(session: dict[str, Any] = Depends(_native_session)):
    with connect() as conn:
        settings = get_team_settings(conn, session["team_id"])
    return services.refresh_sources(sources=settings["enabled_sources"])


@app.post("/api/tournaments/{tournament_id}/teams")
def api_tournament_teams(
    request: Request,
    tournament_id: int,
    age: str,
    division: list[str] | None = Query(default=None),
):
    return services.hydrate_tournament_teams(tournament_id, age, division, team_id=_web_team_id(request))


@app.post("/api/v1/tournaments/{tournament_id}/teams")
def api_v1_tournament_teams(
    tournament_id: int,
    age: str | None = None,
    division: list[str] | None = Query(default=None),
    session: dict[str, Any] = Depends(_native_session),
):
    with connect() as conn:
        settings = get_team_settings(conn, session["team_id"])
    row = services.hydrate_tournament_teams(
        tournament_id,
        age or settings["target_age_division"],
        division,
        team_id=session["team_id"],
    )
    if row is None:
        return api_error("not_found", "Tournament not found.", 404)
    return row


@app.get("/api/changes")
def api_changes(limit: int = 50):
    with connect() as conn:
        return get_changes(conn, limit=limit)


@app.get("/api/v1/changes")
def api_v1_changes(limit: int = 50, session: dict[str, Any] = Depends(_native_session)):
    with connect() as conn:
        return get_changes(conn, limit=limit)


@app.get("/api/refresh-runs")
def api_refresh_runs():
    with connect() as conn:
        return latest_refresh_runs(conn)


@app.get("/api/v1/refresh-runs")
def api_v1_refresh_runs(session: dict[str, Any] = Depends(_native_session)):
    with connect() as conn:
        return latest_refresh_runs(conn)


@app.get("/api/team-stats")
def api_team_stats(age: str | None = None, request: Request = None):
    with connect() as conn:
        settings = get_settings(conn)
        age_division = (age or settings["target_age_division"]).upper()
        teams = stats.aggregate_team_records(conn, age_division)
    return {
        "age": age_division,
        "teams": teams,
        "total_teams": len(teams),
        "note": (
            "NCS records are available for all tournaments. "
            "USSSA and Perfect Game records only appear for tournaments whose team lists have been loaded."
        ),
    }


@app.put("/api/tournaments/{tournament_id}/shortlist")
def api_shortlist(tournament_id: int, payload: dict[str, Any], request: Request):
    with connect() as conn:
        return upsert_shortlist(conn, tournament_id, payload, team_id=_web_team_id(request))


@app.put("/api/v1/tournaments/{tournament_id}/shortlist")
def api_v1_shortlist(
    tournament_id: int,
    payload: ShortlistUpdateRequest,
    session: dict[str, Any] = Depends(_native_session),
):
    with connect() as conn:
        return upsert_shortlist(conn, tournament_id, payload.model_dump(), team_id=session["team_id"])


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
