"""Helpers for checking journal registration in DOAJ."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DOAJ_SEARCH_URL = "https://doaj.org/api/v4/search/journals/"
DOAJ_RECORD_URL = "https://doaj.org/api/v4/journals/{journal_id}"


@dataclass(frozen=True)
class DoajJournalMatch:
    """Result of a DOAJ journal lookup."""

    query: str
    found: bool
    matched_title: str = ""
    record_id: str = ""
    record_url: str = ""
    error: str = ""


class DoajClient:
    """Minimal client for DOAJ journal title lookups."""

    def __init__(
        self, fetcher: Optional[Callable[[str, float], str]] = None, timeout: float = 8.0
    ):
        self.fetcher = fetcher or self._http_get
        self.timeout = timeout

    def lookup_journal(self, journal_title: str) -> DoajJournalMatch:
        cleaned = " ".join(str(journal_title or "").split()).strip()
        if not cleaned:
            return DoajJournalMatch(query="", found=False, error="missing-journal")

        search_query = f'title:"{cleaned}"'
        url = f"{DOAJ_SEARCH_URL}{quote(search_query, safe='')}?page=1&pageSize=1"
        try:
            payload = self.fetcher(url, self.timeout)
        except Exception:
            return DoajJournalMatch(query=cleaned, found=False, error="lookup-failed")

        return self._parse_response(cleaned, payload)

    @staticmethod
    def _http_get(url: str, timeout: float) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": "reference-checker/0.1 (+DOAJ journal lookup)",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                if getattr(response, "status", 200) >= 400:
                    return ""
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="ignore")
        except (HTTPError, URLError):  # pragma: no cover - network failure path
            return ""

    @classmethod
    def _parse_response(cls, query: str, payload: str) -> DoajJournalMatch:
        if not payload:
            return DoajJournalMatch(query=query, found=False, error="lookup-failed")

        try:
            data = json.loads(payload)
        except ValueError:
            return DoajJournalMatch(query=query, found=False, error="lookup-failed")

        total = data.get("total")
        results = data.get("results") or []
        if not isinstance(total, int) or not isinstance(results, list):
            return DoajJournalMatch(query=query, found=False, error="lookup-failed")
        if total <= 0 or not results:
            return DoajJournalMatch(query=query, found=False)

        first = results[0] if isinstance(results[0], dict) else {}
        bibjson = first.get("bibjson") if isinstance(first, dict) else {}
        if not isinstance(bibjson, dict):
            bibjson = {}

        record_id = str(first.get("id") or "").strip()
        matched_title = str(bibjson.get("title") or "").strip()
        record_url = DOAJ_RECORD_URL.format(journal_id=record_id) if record_id else ""

        return DoajJournalMatch(
            query=query,
            found=True,
            matched_title=matched_title,
            record_id=record_id,
            record_url=record_url,
        )


__all__ = ["DoajClient", "DoajJournalMatch"]
