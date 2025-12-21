"""Crossref-backed metadata enrichment and verification helpers."""
from __future__ import annotations

import json
import re
import urllib.parse
from typing import Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .metadata import MetadataProvider
from .models import ReferenceEntry, ValidationIssue


def _normalize_doi(doi: str) -> str:
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = doi.replace("doi:", "")
    return doi


class CrossrefClient:
    """Minimal client for retrieving metadata from Crossref."""

    def __init__(
        self, fetcher: Optional[Callable[[str, float], str]] = None, timeout: float = 6.0
    ):
        self.fetcher = fetcher or self._http_get
        self.timeout = timeout

    def lookup(self, entry: ReferenceEntry) -> Dict[str, object]:
        url = self._build_url(entry)
        if not url:
            return {}

        try:
            payload = self.fetcher(url, self.timeout)
        except Exception:
            return {}

        if not payload:
            return {}

        return self._parse_response(payload)

    @staticmethod
    def _http_get(url: str, timeout: float) -> str:
        request = Request(url, headers={"User-Agent": "reference-checker/0.1"})
        try:
            with urlopen(request, timeout=timeout) as response:
                if getattr(response, "status", 200) >= 400:
                    return ""
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="ignore")
        except (HTTPError, URLError):  # pragma: no cover - network failure path
            return ""

    @staticmethod
    def _build_url(entry: ReferenceEntry) -> Optional[str]:
        if entry.doi:
            return f"https://api.crossref.org/works/{_normalize_doi(entry.doi)}"
        if entry.title:
            query = urllib.parse.quote(entry.title)
            return f"https://api.crossref.org/works?query.title={query}&rows=1"
        return None

    @classmethod
    def _parse_response(cls, payload: str) -> Dict[str, object]:
        try:
            data = json.loads(payload)
        except ValueError:
            return {}

        message = data.get("message")
        if not message:
            return {}
        if isinstance(message, dict) and "items" in message:
            items = message.get("items") or []
            message = items[0] if items else None
        if not isinstance(message, dict):
            return {}

        def first_value(value):
            if isinstance(value, list) and value:
                return value[0]
            if isinstance(value, str):
                return value
            return None

        authors: List[str] = []
        for author in message.get("author", []):
            family = author.get("family")
            given = author.get("given")
            if family and given:
                authors.append(f"{family}, {given}")
            elif family:
                authors.append(family)

        issued = message.get("issued", {})
        year: Optional[str] = None
        if isinstance(issued, dict):
            parts = issued.get("date-parts") or []
            if parts and parts[0]:
                year = str(parts[0][0])

        journal = first_value(message.get("container-title"))
        title = first_value(message.get("title"))
        doi = message.get("DOI")
        pages = message.get("page")

        return {
            "authors": authors,
            "title": title,
            "journal": journal,
            "year": year,
            "volume": message.get("volume"),
            "issue": message.get("issue"),
            "pages": pages,
            "doi": doi,
            "entry_type": message.get("type"),
        }


class CrossrefMetadataProvider(MetadataProvider):
    """Fill missing reference fields using Crossref metadata."""

    name = "crossref"

    def __init__(self, client: Optional[CrossrefClient] = None):
        self.client = client or CrossrefClient()

    def enrich(self, entry: ReferenceEntry) -> ReferenceEntry:
        metadata = self.client.lookup(entry)
        if not metadata:
            return entry

        if metadata.get("authors") and not entry.authors:
            entry.authors = list(metadata["authors"])  # type: ignore[assignment]

        for field in [
            "title",
            "journal",
            "year",
            "volume",
            "issue",
            "pages",
            "doi",
            "entry_type",
        ]:
            value = metadata.get(field)
            if value and getattr(entry, field) in (None, ""):
                setattr(entry, field, value)  # type: ignore[arg-type]
        return entry


class OnlineReferenceVerifier:
    """Compare local reference details against authoritative Crossref metadata."""

    def __init__(self, client: Optional[CrossrefClient] = None):
        self.client = client or CrossrefClient()

    def verify(self, entry: ReferenceEntry) -> List[ValidationIssue]:
        metadata = self.client.lookup(entry)
        if not metadata:
            return []

        issues: List[ValidationIssue] = []

        def mismatch(code: str, detail: str) -> None:
            issues.append(
                ValidationIssue(
                    code=code,
                    message=detail,
                    context=entry.raw_text,
                    severity="error",
                )
            )

        if entry.doi and metadata.get("doi"):
            if _normalize_doi(entry.doi) != _normalize_doi(str(metadata["doi"])):
                mismatch("doi-mismatch", f"DOI points to {metadata['doi']} online")

        if entry.title and metadata.get("title"):
            if not self._same_text(entry.title, str(metadata["title"])):
                mismatch("title-mismatch", f"Online title: {metadata['title']}")

        if entry.authors and metadata.get("authors"):
            recorded = entry.authors[0].split(",")[0].strip().lower()
            fetched = str(metadata["authors"][0]).split(",")[0].strip().lower()
            if recorded and fetched and recorded != fetched:
                mismatch("author-mismatch", f"First author online: {metadata['authors'][0]}")

        if entry.journal and metadata.get("journal"):
            if not self._same_text(entry.journal, str(metadata["journal"])):
                mismatch("journal-mismatch", f"Online venue: {metadata['journal']}")

        if entry.year and metadata.get("year"):
            if str(entry.year).strip() != str(metadata["year"]).strip():
                mismatch("year-mismatch", f"Online year: {metadata['year']}")

        return issues

    @staticmethod
    def _same_text(a: str, b: str) -> bool:
        return " ".join(a.lower().split()) == " ".join(b.lower().split())


__all__ = [
    "CrossrefClient",
    "CrossrefMetadataProvider",
    "OnlineReferenceVerifier",
]
