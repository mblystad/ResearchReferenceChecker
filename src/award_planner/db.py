from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import AvailabilityResponse, SearchParams

DB_PATH = Path("data/app.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            params_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS search_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            saved_search_id INTEGER NOT NULL REFERENCES saved_searches(id),
            run_at TEXT NOT NULL,
            response_hash TEXT NOT NULL,
            response_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            saved_search_id INTEGER NOT NULL REFERENCES saved_searches(id),
            last_notified_at TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            channels_json TEXT
        );

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            itinerary_key TEXT UNIQUE NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            itinerary_json TEXT
        );

        CREATE TABLE IF NOT EXISTS cached_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE NOT NULL,
            response_json TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def save_search(conn: sqlite3.Connection, name: str, params: SearchParams) -> int:
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "INSERT INTO saved_searches (name, params_json, created_at) VALUES (?, ?, ?)",
        (name, params.json(), now),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_saved_searches(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, params_json, created_at FROM saved_searches ORDER BY created_at DESC"
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "params": SearchParams.parse_raw(row["params_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def save_search_run(
    conn: sqlite3.Connection, saved_search_id: int, response: AvailabilityResponse
) -> int:
    payload = response.json()
    cursor = conn.execute(
        "INSERT INTO search_runs (saved_search_id, run_at, response_hash, response_json)"
        " VALUES (?, ?, ?, ?)",
        (saved_search_id, datetime.utcnow().isoformat(), response.digest(), payload),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_last_run(conn: sqlite3.Connection, saved_search_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM search_runs WHERE saved_search_id = ? ORDER BY run_at DESC LIMIT 1",
        (saved_search_id,),
    ).fetchone()


def upsert_alert(conn: sqlite3.Connection, saved_search_id: int, channels: List[str]) -> None:
    channels_json = json.dumps(channels)
    existing = conn.execute(
        "SELECT id FROM alerts WHERE saved_search_id = ?", (saved_search_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE alerts SET enabled = 1, channels_json = ? WHERE saved_search_id = ?",
            (channels_json, saved_search_id),
        )
    else:
        conn.execute(
            "INSERT INTO alerts (saved_search_id, enabled, channels_json) VALUES (?, 1, ?)",
            (saved_search_id, channels_json),
        )
    conn.commit()


def enabled_alerts(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT a.id, a.saved_search_id, a.last_notified_at, a.channels_json,"
        " s.name, s.params_json"
        " FROM alerts a JOIN saved_searches s ON s.id = a.saved_search_id"
        " WHERE a.enabled = 1"
        " ORDER BY a.id"
    ).fetchall()
    return [
        {
            "alert_id": row["id"],
            "saved_search_id": row["saved_search_id"],
            "last_notified_at": row["last_notified_at"],
            "channels": json.loads(row["channels_json"]) if row["channels_json"] else [],
            "name": row["name"],
            "params": SearchParams.parse_raw(row["params_json"]),
        }
        for row in rows
    ]


def record_notification(conn: sqlite3.Connection, alert_id: int) -> None:
    conn.execute(
        "UPDATE alerts SET last_notified_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), alert_id),
    )
    conn.commit()


def add_favorite(conn: sqlite3.Connection, itinerary_key: str, itinerary_json: str, notes: str = "") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO favorites (itinerary_key, notes, created_at, itinerary_json)"
        " VALUES (?, ?, ?, ?)",
        (itinerary_key, notes, datetime.utcnow().isoformat(), itinerary_json),
    )
    conn.commit()


def list_favorites(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT itinerary_key, notes, created_at, itinerary_json FROM favorites ORDER BY created_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def get_cached_response(conn: sqlite3.Connection, cache_key: str) -> Optional[str]:
    row = conn.execute(
        "SELECT response_json, expires_at FROM cached_responses WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if not row:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.utcnow():
        conn.execute("DELETE FROM cached_responses WHERE cache_key = ?", (cache_key,))
        conn.commit()
        return None
    return row["response_json"]


def set_cached_response(conn: sqlite3.Connection, cache_key: str, response_json: str, ttl_hours: int) -> None:
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    conn.execute(
        "INSERT INTO cached_responses (cache_key, response_json, expires_at)"
        " VALUES (?, ?, ?)"
        " ON CONFLICT(cache_key) DO UPDATE SET response_json = excluded.response_json,"
        " expires_at = excluded.expires_at",
        (cache_key, response_json, expires_at.isoformat()),
    )
    conn.commit()
