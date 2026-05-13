from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import time
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from baseball_aggregator.config import auth_enabled, dev_auto_login, get_admin_password, is_hosted_mode
from baseball_aggregator.storage import connect, create_team, verify_team_password

log = logging.getLogger(__name__)

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


def login_page(error: str = "", signup_error: str = "") -> HTMLResponse:
    error_html = f'<p class="error">{_escape(error)}</p>' if error else ""
    signup_error_html = f'<p class="error">{_escape(signup_error)}</p>' if signup_error else ""
    setup_open = "open" if signup_error else ""
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tournament IQ</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body class="login-page">
  <main class="login-shell">
    <form class="login-card" method="post" action="/login">
      <h1>Tournament IQ</h1>
      <p class="subtle">Enter your team code and password to sign in.</p>
      {error_html}
      <label>Team code
        <input name="team_slug" autocomplete="organization" placeholder="8u-hawks">
      </label>
      <label>Password
        <input name="password" type="password" autocomplete="current-password" autofocus required>
      </label>
      <button class="primary" type="submit">Sign in</button>
    </form>

    <details class="setup-card" id="setupPanel" {setup_open}>
      <summary class="setup-summary">Set up a new team</summary>
      <form class="setup-form" method="post" action="/signup" id="signupForm" novalidate>
        {signup_error_html}
        <div class="signup-preview" id="signupPreview"></div>
        <label>Team code
          <input name="team_slug" id="slugInput" placeholder="8u-hawks" autocomplete="off" spellcheck="false">
          <span class="field-hint">Lowercase letters, numbers, hyphens. 2&ndash;30 characters.</span>
          <span class="field-hint error" id="slugError" hidden></span>
        </label>
        <label>Team name
          <input name="display_name" id="displayNameInput" placeholder="Hawks 8U" required>
        </label>
        <label>Password
          <input name="password" id="pwInput" type="password" autocomplete="new-password" required>
          <span class="field-hint">At least 8 characters.</span>
        </label>
        <label>Confirm password
          <input name="confirm_password" id="pw2Input" type="password" autocomplete="new-password" required>
          <span class="field-hint error" id="pwError" hidden></span>
        </label>
        <div class="logo-upload-row">
          <span class="field-label">Team logo <span class="field-hint optional">(optional &mdash; used to extract brand colors)</span></span>
          <label class="logo-upload-btn" for="logoFile">Choose image&hellip;</label>
          <input type="file" id="logoFile" accept="image/*" class="logo-file-input">
          <span id="logoFileName" class="field-hint"></span>
        </div>
        <div class="color-row">
          <label class="color-label">Primary
            <input type="color" name="brand_primary" id="colorPrimary" value="#6750A4">
          </label>
          <label class="color-label">Secondary
            <input type="color" name="brand_secondary" id="colorSecondary" value="#625B71">
          </label>
          <label class="color-label">Accent
            <input type="color" name="brand_accent" id="colorAccent" value="#7D5260">
          </label>
        </div>
        <input type="hidden" name="logo_url" id="logoUrlInput">
        <button class="primary" type="submit" id="signupSubmitBtn">Create team &amp; sign in</button>
      </form>
    </details>
  </main>
  <script src="/static/utils.js"></script>
  <script src="/static/login.js"></script>
</body>
</html>"""
    )


async def handle_login(request: Request) -> Response:
    payload = parse_qs((await request.body()).decode("utf-8"))
    team_slug = payload.get("team_slug", [""])[0].strip().lower()
    password = payload.get("password", [""])[0]
    team_id = "default"
    if team_slug == "default" or not team_slug:
        # Admin login (explicit "default" slug or legacy blank slug): must match ADMIN_PASSWORD env var
        admin_pw = get_admin_password()
        if not admin_pw or not hmac.compare_digest(password, admin_pw):
            log.warning("Failed admin login attempt")
            return login_page("Team code or password did not match.")
        log.info("Successful admin login")
    elif team_slug:
        with connect() as conn:
            team = verify_team_password(conn, team_slug, password)
        if team is None:
            log.warning("Failed web login attempt for team slug %r", team_slug)
            return login_page("Team code or password did not match.")
        log.info("Successful web login for team %r (id=%s)", team_slug, team["id"])
        team_id = team["id"]

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


async def handle_signup(request: Request) -> Response:
    payload = parse_qs((await request.body()).decode("utf-8"))
    team_slug       = payload.get("team_slug",        [""])[0].strip().lower()
    display_name    = payload.get("display_name",     [""])[0].strip()
    password        = payload.get("password",         [""])[0]
    confirm_pw      = payload.get("confirm_password", [""])[0]
    brand_primary   = payload.get("brand_primary",    ["#6750A4"])[0].strip()
    brand_secondary = payload.get("brand_secondary",  ["#625B71"])[0].strip()
    brand_accent    = payload.get("brand_accent",     ["#7D5260"])[0].strip()
    logo_url        = payload.get("logo_url",         [""])[0].strip()

    _SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,29}$")
    if not _SLUG_RE.match(team_slug) or team_slug == "default":
        return login_page(signup_error="Team code must be 2–30 lowercase letters, numbers, or hyphens.")
    if len(display_name) < 2:
        return login_page(signup_error="Team name must be at least 2 characters.")
    if len(password) < 8:
        return login_page(signup_error="Password must be at least 8 characters.")
    if password != confirm_pw:
        return login_page(signup_error="Passwords do not match.")

    settings: dict = {
        "brand_primary":   brand_primary   or "#6750A4",
        "brand_secondary": brand_secondary or "#625B71",
        "brand_accent":    brand_accent    or "#7D5260",
    }
    if logo_url.startswith("data:image/") and len(logo_url) < 200_000:
        settings["logo_url"] = logo_url

    with connect() as conn:
        existing = conn.execute("SELECT id FROM teams WHERE slug = ?", (team_slug,)).fetchone()
        if existing:
            return login_page(signup_error=f"Team code '{_escape(team_slug)}' is already taken.")
        team = create_team(conn, slug=team_slug, display_name=display_name,
                           password=password, settings=settings)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        _sign_session(int(time.time()), team["id"]),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=is_hosted_mode(),
        samesite="lax",
    )
    return response


def _is_public_path(path: str) -> bool:
    return path in {"/login", "/logout", "/signup", "/api/v1/login"} or path.startswith("/static/")


def _has_bearer_token(request: Request) -> bool:
    value = request.headers.get("authorization", "")
    return value.lower().startswith("bearer ")


def _valid_session(cookie_value: str | None) -> bool:
    team_id = get_web_team_id(cookie_value)
    if team_id is None:
        return False
    if team_id == "default":
        return True
    with connect() as conn:
        row = conn.execute("SELECT active FROM teams WHERE id = ?", (team_id,)).fetchone()
    return bool(row and row["active"])


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
