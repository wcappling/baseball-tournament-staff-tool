from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL_DATA_DIR = ROOT / "data"


def get_data_dir() -> Path:
    configured = os.getenv("STAFF_TOOL_DATA_DIR")
    return Path(configured).expanduser() if configured else LOCAL_DATA_DIR


def get_db_path() -> Path:
    return get_data_dir() / "baseball_staff_tool.sqlite3"


def get_backup_dir() -> Path:
    return get_data_dir() / "backups"


def is_hosted_mode() -> bool:
    return os.getenv("STAFF_TOOL_HOSTED", "").lower() in {"1", "true", "yes"} or bool(
        os.getenv("RAILWAY_ENVIRONMENT")
    )


def dev_auto_login() -> bool:
    """Skip the login screen entirely. Set DEV_AUTO_LOGIN=true in Railway Dev only."""
    return os.getenv("DEV_AUTO_LOGIN", "").lower() in {"1", "true", "yes"}


def auth_enabled() -> bool:
    return bool(os.getenv("STAFF_TOOL_PASSWORD")) or is_hosted_mode()


def get_admin_password() -> str:
    """Password required to log in as the default admin account.
    Set ADMIN_PASSWORD on Railway to control admin access via env var."""
    return os.getenv("ADMIN_PASSWORD", "")


def hosted_jobs_enabled() -> bool:
    value = os.getenv("STAFF_TOOL_ENABLE_HOSTED_JOBS")
    if value is not None:
        return value.lower() in {"1", "true", "yes"}
    return is_hosted_mode()


def get_allowed_origins() -> list[str]:
    """CORS allowed origins: always localhost; Railway URL auto-detected; explicit overrides via ALLOWED_ORIGINS."""
    origins = ["http://localhost", "http://127.0.0.1", "http://localhost:8000"]
    railway_url = os.getenv("RAILWAY_STATIC_URL")
    if railway_url:
        url = railway_url.rstrip("/")
        if not url.startswith("http"):
            url = f"https://{url}"
        origins.append(url)
    extra = os.getenv("ALLOWED_ORIGINS", "")
    if extra:
        origins.extend(u.strip() for u in extra.split(",") if u.strip())
    return origins


def require_hosted_config() -> None:
    if not is_hosted_mode():
        return

    missing = [
        name
        for name in ("STAFF_TOOL_PASSWORD", "SESSION_SECRET", "STAFF_TOOL_DATA_DIR", "ADMIN_PASSWORD")
        if not os.getenv(name)
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Hosted mode is missing required environment variable(s): {joined}. "
            "Set these before starting the app so auth and persistent SQLite storage are safe."
        )
