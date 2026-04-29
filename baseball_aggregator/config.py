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


def auth_enabled() -> bool:
    return bool(os.getenv("STAFF_TOOL_PASSWORD")) or is_hosted_mode()


def hosted_jobs_enabled() -> bool:
    value = os.getenv("STAFF_TOOL_ENABLE_HOSTED_JOBS")
    if value is not None:
        return value.lower() in {"1", "true", "yes"}
    return is_hosted_mode()


def require_hosted_config() -> None:
    if not is_hosted_mode():
        return

    missing = [
        name
        for name in ("STAFF_TOOL_PASSWORD", "SESSION_SECRET", "STAFF_TOOL_DATA_DIR")
        if not os.getenv(name)
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Hosted mode is missing required environment variable(s): {joined}. "
            "Set these before starting the app so auth and persistent SQLite storage are safe."
        )
