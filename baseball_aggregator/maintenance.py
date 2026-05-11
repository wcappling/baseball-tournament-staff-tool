from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from baseball_aggregator.config import get_backup_dir, get_db_path


def create_sqlite_backup(db_path: Path | None = None, backup_dir: Path | None = None) -> Path | None:
    source_path = db_path or get_db_path()
    if not source_path.exists():
        return None

    destination_dir = backup_dir or get_backup_dir()
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    destination = destination_dir / f"baseball_staff_tool-{timestamp}.sqlite3"

    with sqlite3.connect(source_path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    try:
        os.chmod(destination, 0o600)
    except OSError:
        pass
    return destination


def prune_backups(backup_dir: Path | None = None, keep: int = 7) -> list[Path]:
    target_dir = backup_dir or get_backup_dir()
    if not target_dir.exists():
        return []
    backups = sorted(
        target_dir.glob("baseball_staff_tool-*.sqlite3"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    for path in backups[keep:]:
        path.unlink(missing_ok=True)
        removed.append(path)
    return removed
