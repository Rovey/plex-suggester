"""SQLite storage for suggestion history and exclude list."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from plex_suggester.config import get_data_dir


def _get_db() -> sqlite3.Connection:
    db_path = get_data_dir() / "history.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            mode TEXT NOT NULL,
            suggestion_type TEXT NOT NULL,
            total_minutes INTEGER NOT NULL,
            movies_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS excluded_movies (
            rating_key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            reason TEXT DEFAULT '',
            excluded_at TEXT NOT NULL
        );
    """)


# ── Exclude list ──────────────────────────────────────────────────────────────

def exclude_movie(rating_key: str, title: str, reason: str = "") -> None:
    """Add a movie to the exclude list."""
    conn = _get_db()
    conn.execute(
        "INSERT OR REPLACE INTO excluded_movies (rating_key, title, reason, excluded_at) VALUES (?, ?, ?, ?)",
        (rating_key, title, reason, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def unexclude_movie(rating_key: str) -> bool:
    """Remove a movie from the exclude list. Returns True if it was found."""
    conn = _get_db()
    cursor = conn.execute("DELETE FROM excluded_movies WHERE rating_key = ?", (rating_key,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def get_excluded_movies() -> list[dict]:
    """Return all excluded movies."""
    conn = _get_db()
    rows = conn.execute("SELECT rating_key, title, reason, excluded_at FROM excluded_movies ORDER BY excluded_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_excluded_keys() -> set[str]:
    """Return set of excluded rating keys (for fast filtering)."""
    conn = _get_db()
    rows = conn.execute("SELECT rating_key FROM excluded_movies").fetchall()
    conn.close()
    return {r["rating_key"] for r in rows}


# ── Suggestion history ────────────────────────────────────────────────────────

def save_suggestion(mode: str, suggestion_type: str, total_minutes: int, movies: list[dict]) -> int:
    """Save a suggestion to history. Returns the suggestion ID."""
    conn = _get_db()
    cursor = conn.execute(
        "INSERT INTO suggestions (created_at, mode, suggestion_type, total_minutes, movies_json) VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            mode,
            suggestion_type,
            total_minutes,
            json.dumps(movies, ensure_ascii=False),
        ),
    )
    conn.commit()
    suggestion_id = cursor.lastrowid
    conn.close()
    return suggestion_id


def get_history(limit: int = 20) -> list[dict]:
    """Return recent suggestions."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, created_at, mode, suggestion_type, total_minutes, movies_json FROM suggestions ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    results = []
    for r in rows:
        entry = dict(r)
        entry["movies"] = json.loads(entry["movies_json"])
        del entry["movies_json"]
        results.append(entry)
    return results


def get_suggestion_by_id(suggestion_id: int) -> dict | None:
    """Return a single suggestion by ID."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, created_at, mode, suggestion_type, total_minutes, movies_json FROM suggestions WHERE id = ?",
        (suggestion_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    entry = dict(row)
    entry["movies"] = json.loads(entry["movies_json"])
    del entry["movies_json"]
    return entry
