from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .version import __version__


BACKUP_FORMAT = "tapestries-muck-settings"
BACKUP_VERSION = 1


def write_backup(db, path: str | Path) -> None:
    document = {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_VERSION,
        "app_version": __version__,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "data": db.export_personal_data(),
    }
    Path(path).write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")


def read_backup(path: str | Path) -> dict:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read this JSON backup: {exc}") from exc
    if not isinstance(document, dict) or document.get("format") != BACKUP_FORMAT:
        raise ValueError("This is not a Tapestries MUCK settings backup.")
    if document.get("format_version") != BACKUP_VERSION:
        raise ValueError("This backup uses an unsupported format version.")
    data = document.get("data")
    if not isinstance(data, dict):
        raise ValueError("The backup has no valid data section.")
    if not isinstance(data.get("settings", {}), dict):
        raise ValueError("The settings section is invalid.")
    for name in ("keywords", "known_users"):
        if not isinstance(data.get(name, []), list) or not all(isinstance(row, dict) for row in data.get(name, [])):
            raise ValueError(f"The {name} section is invalid.")
    required_keyword = {"keyword", "enabled", "case_sensitive", "whole_word", "color"}
    if any(not required_keyword.issubset(row) for row in data.get("keywords", [])):
        raise ValueError("A keyword entry is incomplete.")
    if any("username" not in row for row in data.get("known_users", [])):
        raise ValueError("A known-user entry is incomplete.")
    return data
