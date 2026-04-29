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

from baseball_aggregator.config import auth_enabled, is_hosted_mode

COOKIE_NAME = "baseball_staff_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not auth_enabled() or _is_public_path(request.url.path):
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
      <p class="subtle">Enter the shared staff password.</p>
      {error_html}
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
    password = payload.get("password", [""])[0]
    expected = os.getenv("STAFF_TOOL_PASSWORD", "")
    if not expected or not hmac.compare_digest(password, expected):
        return login_page("Password did not match.")

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        _sign_session(int(time.time())),
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
    return path in {"/login", "/logout"} or path.startswith("/static/")


def _valid_session(cookie_value: str | None) -> bool:
    if not cookie_value:
        return False
    try:
        timestamp_raw, signature = cookie_value.split(".", 1)
        timestamp = int(timestamp_raw)
    except ValueError:
        return False
    if time.time() - timestamp > SESSION_MAX_AGE_SECONDS:
        return False
    if timestamp > time.time() + 60:
        return False
    return hmac.compare_digest(signature, _signature(timestamp_raw))


def _sign_session(timestamp: int) -> str:
    raw = str(timestamp)
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
