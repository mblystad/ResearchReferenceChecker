"""Helpers for loading and querying journal abbreviation datasets."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List
import json
import sqlite3

from .normalization import normalize_text

ABBR_JSON_FILENAME = "abbr_to_full.json"
ABBR_SQLITE_FILENAME = "abbr_to_full.sqlite"


def load_abbreviation_index(paths: Iterable[Path]) -> Dict[str, List[str]]:
    """Load abbreviation mappings from JSON and/or SQLite files."""
    index: Dict[str, List[str]] = {}
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".json":
            _merge_json(path, index)
        elif suffix in {".sqlite", ".db"}:
            _merge_sqlite(path, index)
    return index


def abbreviation_candidates(
    index: Dict[str, List[str]], value: str | None, *, limit: int = 15
) -> List[str]:
    """Return candidate full titles for a possible journal abbreviation."""
    normalized = normalize_text(value)
    if not normalized:
        return []
    candidates = index.get(normalized, [])
    if limit <= 0:
        return list(candidates)
    return list(candidates[:limit])


def _merge_json(path: Path, index: Dict[str, List[str]]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return

    mapping = data.get("abbr_to_full") if isinstance(data, dict) and "abbr_to_full" in data else data
    if not isinstance(mapping, dict):
        return

    for key, value in mapping.items():
        key_norm = normalize_text(str(key))
        if not key_norm:
            continue
        titles = _coerce_titles(value)
        for title in titles:
            _append_unique(index, key_norm, title)


def _merge_sqlite(path: Path, index: Dict[str, List[str]]) -> None:
    try:
        con = sqlite3.connect(str(path))
    except sqlite3.Error:
        return

    try:
        rows = con.execute("SELECT abbr_norm, full_title FROM abbr_map").fetchall()
    except sqlite3.Error:
        con.close()
        return

    for key, title in rows:
        key_norm = normalize_text(str(key))
        title_str = str(title).strip()
        if key_norm and title_str:
            _append_unique(index, key_norm, title_str)
    con.close()


def _coerce_titles(value: object) -> List[str]:
    if isinstance(value, str):
        title = value.strip()
        return [title] if title else []
    if isinstance(value, list):
        results: List[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                results.append(item.strip())
        return results
    return []


def _append_unique(index: Dict[str, List[str]], key: str, title: str) -> None:
    bucket = index.setdefault(key, [])
    if title not in bucket:
        bucket.append(title)
