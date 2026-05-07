from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from baseball_aggregator.config import auth_enabled, dev_auto_login, is_hosted_mode
from baseball_aggregator.storage import connect, verify_team_password

COOKIE_NAME = "baseball_staff_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not auth_enabled() or _is_public_path(request.url.path) or dev_auto_login():
            return await call_next(request)

        if request.url.path.startswith("/api/v1/") and _has_bearer_token(request):
            return await call_next(request)

        if _valid_session(request.cookies.get(COOKIE_NAME)):
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return RedirectResponse("/login", status_code=303)


def login_page(error: str = "") -> HTMLResponse:
    error_html = f'<p class="error">{_escape(error)}</p>' if error else ""
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Staff Login</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body class="login-page">
  <main class="login-shell">
    <form class="login-card" method="post" action="/login">
      <h1>Tournament Staff Tool</h1>
      <p class="subtle">Enter your team code and shared staff password.</p>
      {error_html}
      <label>Team code
        <input name="team_slug" autocomplete="organization" placeholder="8u-hawks">
      </label>
      <label>Password
        <input name="password" type="password" autocomplete="current-password" autofocus required>
      </label>
      <button class="primary" type="submit">Sign in</button>
    </form>
  </main>
</body>
</html>"""
    )


async def handle_login(request: Request) -> Response:
    payload = parse_qs((await request.body()).decode("utf-8"))
    team_slug = payload.get("team_slug", [""])[0].strip()
    password = payload.get("password", [""])[0]
    team_id = "default"
    if team_slug:
        with connect() as conn:
            team = verify_team_password(conn, team_slug, password)
        if team is None:
            return login_page("Team code or password did not match.")
        team_id = team["id"]
    else:
        expected = os.getenv("STAFF_TOOL_PASSWORD", "")
        if not expected or not hmac.compare_digest(password, expected):
            return login_page("Password did not match.")

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        _sign_session(int(time.time()), team_id),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=is_hosted_mode(),
        samesite="lax",
    )
    return response


def handle_logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


def _is_public_path(path: str) -> bool:
    return path in {"/login", "/logout", "/api/v1/login"} or path.startswith("/static/")


def _has_bearer_token(request: Request) -> bool:
    value = request.headers.get("authorization", "")
    return value.lower().startswith("bearer ")


def _valid_session(cookie_value: str | None) -> bool:
    return get_web_team_id(cookie_value) is not None


def get_web_team_id(cookie_value: str | None) -> str | None:
    if not cookie_value:
        return None
    try:
        raw, signature = cookie_value.rsplit(".", 1)
        parts = raw.split(".", 1)
        timestamp_raw = parts[0]
        team_id = parts[1] if len(parts) > 1 else "default"
        timestamp = int(timestamp_raw)
    except ValueError:
        return None
    if time.time() - timestamp > SESSION_MAX_AGE_SECONDS:
        return None
    if timestamp > time.time() + 60:
        return None
    if not hmac.compare_digest(signature, _signature(raw)):
        return None
    return team_id


def _sign_session(timestamp: int, team_id: str = "default") -> str:
    raw = f"{timestamp}.{team_id}"
    return f"{raw}.{_signature(raw)}"


def _signature(value: str) -> str:
    secret = os.getenv("SESSION_SECRET") or "local-development-session-secret"
    digest = hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )
