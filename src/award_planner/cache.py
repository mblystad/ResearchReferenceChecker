from __future__ import annotations

import hashlib
from typing import Optional

import sqlite3

from .db import get_cached_response, set_cached_response
from .models import SearchParams


def cache_key(params: SearchParams) -> str:
    normalized = params.normalized()
    return hashlib.sha256(normalized.encode()).hexdigest()


def get_cached(conn: sqlite3.Connection, params: SearchParams) -> Optional[str]:
    return get_cached_response(conn, cache_key(params))


def set_cache(conn: sqlite3.Connection, params: SearchParams, response_json: str, ttl_hours: int) -> None:
    set_cached_response(conn, cache_key(params), response_json, ttl_hours)
