from __future__ import annotations

import os
import sys
import sqlite3
from pathlib import Path


APP_NAME = "Tapestries MUCK Client"


def _is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def _user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def resolve_database_path(path: str | Path = "client_data.sqlite3") -> Path:
    db_path = Path(path)
    if db_path.is_absolute() or not _is_frozen_app():
        return db_path

    return _user_data_dir() / db_path.name


class Database:
    def __init__(self, path: str | Path = "client_data.sqlite3") -> None:
        self.path = resolve_database_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS keywords (
                keyword TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                case_sensitive INTEGER NOT NULL DEFAULT 0,
                whole_word INTEGER NOT NULL DEFAULT 1,
                color TEXT NOT NULL DEFAULT '#5dade2'
            );

            CREATE TABLE IF NOT EXISTS known_users (
                username TEXT PRIMARY KEY,
                gender TEXT,
                color TEXT
            );
            """
        )
        self._ensure_column("keywords", "color", "TEXT NOT NULL DEFAULT '#5dade2'")
        self._ensure_column("known_users", "color", "TEXT")
        self.conn.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = [row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in columns:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def get_all_settings(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def export_personal_data(self) -> dict:
        return {
            "settings": self.get_all_settings(),
            "keywords": [dict(row) for row in self.list_keywords()],
            "known_users": [dict(row) for row in self.list_known_users()],
        }

    def import_personal_data(self, data: dict, replace: bool = False) -> None:
        """Import a validated backup atomically.

        Merge updates matching keys/names and preserves unrelated local rows.
        Replace clears all personal configuration before importing.
        """
        settings = data.get("settings", {})
        keywords = data.get("keywords", [])
        known_users = data.get("known_users", [])
        with self.conn:
            if replace:
                self.conn.execute("DELETE FROM settings")
                self.conn.execute("DELETE FROM keywords")
                self.conn.execute("DELETE FROM known_users")
            for key, value in settings.items():
                self.conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
            for row in keywords:
                self.conn.execute(
                    """INSERT INTO keywords(keyword, enabled, case_sensitive, whole_word, color)
                    VALUES(?, ?, ?, ?, ?) ON CONFLICT(keyword) DO UPDATE SET
                    enabled=excluded.enabled, case_sensitive=excluded.case_sensitive,
                    whole_word=excluded.whole_word, color=excluded.color""",
                    (row["keyword"], row["enabled"], row["case_sensitive"], row["whole_word"], row["color"]),
                )
            for row in known_users:
                self.conn.execute(
                    """INSERT INTO known_users(username, gender, color) VALUES(?, ?, ?)
                    ON CONFLICT(username) DO UPDATE SET gender=excluded.gender, color=excluded.color""",
                    (row["username"], row.get("gender"), row.get("color")),
                )

    def list_keywords(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT keyword, enabled, case_sensitive, whole_word, color
            FROM keywords
            ORDER BY keyword COLLATE NOCASE
            """
        ).fetchall()

    def add_keyword(
        self,
        keyword: str,
        case_sensitive: bool = False,
        whole_word: bool = True,
        color: str = "#a8e6a3",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO keywords(keyword, enabled, case_sensitive, whole_word, color)
            VALUES(?, 1, ?, ?, ?)
            ON CONFLICT(keyword) DO UPDATE SET
                enabled=1,
                case_sensitive=excluded.case_sensitive,
                whole_word=excluded.whole_word,
                color=excluded.color
            """,
            (keyword, int(case_sensitive), int(whole_word), color),
        )
        self.conn.commit()

    def update_keyword(
        self,
        old_keyword: str,
        new_keyword: str,
        enabled: bool,
        case_sensitive: bool,
        whole_word: bool,
        color: str,
    ) -> None:
        if old_keyword == new_keyword:
            self.conn.execute(
                """
                UPDATE keywords
                SET enabled=?, case_sensitive=?, whole_word=?, color=?
                WHERE keyword=?
                """,
                (int(enabled), int(case_sensitive), int(whole_word), color, old_keyword),
            )
        else:
            self.conn.execute("DELETE FROM keywords WHERE keyword=?", (old_keyword,))
            self.conn.execute(
                """
                INSERT INTO keywords(keyword, enabled, case_sensitive, whole_word, color)
                VALUES(?, ?, ?, ?, ?)
                """,
                (new_keyword, int(enabled), int(case_sensitive), int(whole_word), color),
            )
        self.conn.commit()

    def delete_keyword(self, keyword: str) -> None:
        self.conn.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
        self.conn.commit()

    def list_known_users(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT username, gender, color FROM known_users ORDER BY username COLLATE NOCASE"
        ).fetchall()

    def add_known_user(self, username: str, gender: str | None = None, color: str | None = None) -> None:
        self.conn.execute(
            """
            INSERT INTO known_users(username, gender, color) VALUES(?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                gender=COALESCE(excluded.gender, known_users.gender),
                color=COALESCE(excluded.color, known_users.color)
            """,
            (username, gender, color),
        )
        self.conn.commit()

    def update_known_user(self, old_username: str, username: str, gender: str | None, color: str | None) -> None:
        if old_username == username:
            self.conn.execute(
                "UPDATE known_users SET gender=?, color=? WHERE username=?",
                (gender, color, old_username),
            )
        else:
            self.conn.execute("DELETE FROM known_users WHERE username=?", (old_username,))
            self.conn.execute(
                "INSERT INTO known_users(username, gender, color) VALUES(?, ?, ?)",
                (username, gender, color),
            )
        self.conn.commit()

    def delete_known_user(self, username: str) -> None:
        self.conn.execute("DELETE FROM known_users WHERE username = ?", (username,))
        self.conn.commit()

    def replace_known_users(self, users: list[tuple[str, str | None]]) -> None:
        """Upsert room users learned from `who`/`whom`.

        This intentionally resets auto-learned gender to the parser's value
        instead of preserving older `ws`-learned gender values, because `who`
        does not provide gender and should not cause gender-color highlighting.
        User-picked colors are preserved.
        """
        for username, gender in users:
            self.conn.execute(
                """
                INSERT INTO known_users(username, gender, color) VALUES(?, ?, NULL)
                ON CONFLICT(username) DO UPDATE SET
                    gender=excluded.gender,
                    color=known_users.color
                """,
                (username, gender),
            )
        self.conn.commit()
