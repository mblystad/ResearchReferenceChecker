"""Simple web page scraper to enrich missing reference metadata."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .metadata import MetadataProvider
from .models import ReferenceEntry


class _MetaParser(HTMLParser):
    """Lightweight HTML parser that captures meta tags and title text."""

    def __init__(self) -> None:
        super().__init__()
        self.meta_tags: list[dict[str, str]] = []
        self.title: Optional[str] = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # pragma: no cover - passthrough
        if tag.lower() == "meta":
            self.meta_tags.append({k.lower(): v for k, v in attrs if v is not None})
        elif tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:  # pragma: no cover - passthrough
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:  # pragma: no cover - passthrough
        if self._in_title:
            text = data.strip()
            if text:
                self.title = (self.title or "") + text


class WebPageMetadataProvider(MetadataProvider):
    """Fetch and parse HTML metadata to fill missing reference fields."""

    name = "web_page"

    def __init__(
        self, fetcher: Optional[Callable[[str, float], str]] = None, timeout: float = 6.0
    ):
        self.fetcher = fetcher or self._http_get
        self.timeout = timeout

    def enrich(self, entry: ReferenceEntry) -> ReferenceEntry:
        target = self._target_url(entry)
        if not target:
            return entry

        try:
            html = self.fetcher(target, self.timeout)
        except Exception:
            return entry

        if not html:
            return entry

        parser = _MetaParser()
        parser.feed(html)
        scraped = self._extract_metadata(parser)
        return self._apply(entry, scraped)

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
    def _target_url(entry: ReferenceEntry) -> Optional[str]:
        if entry.url:
            return entry.url
        if entry.doi:
            return f"https://doi.org/{entry.doi}"
        return None

    @staticmethod
    def _extract_metadata(parser: _MetaParser) -> Dict[str, object]:
        metadata: Dict[str, object] = {}

        def meta(name: str) -> Optional[str]:
            for tag in parser.meta_tags:
                if tag.get("name") == name.lower() and tag.get("content"):
                    return tag["content"].strip()
            return None

        def meta_property(prop: str) -> Optional[str]:
            for tag in parser.meta_tags:
                if tag.get("property") == prop and tag.get("content"):
                    return tag["content"].strip()
            return None

        title = meta("citation_title") or meta("dc.title") or meta_property("og:title")
        if not title and parser.title:
            title = parser.title.strip()
        if title:
            metadata["title"] = title

        authors = [
            tag["content"].strip()
            for tag in parser.meta_tags
            if tag.get("name") == "citation_author" and tag.get("content")
        ]
        if authors:
            metadata["authors"] = authors

        journal = meta("citation_journal_title") or meta("citation_conference_title")
        if journal:
            metadata["journal"] = journal

        doi = meta("citation_doi")
        if doi:
            metadata["doi"] = doi

        year = meta("citation_year") or meta("dc.date")
        if not year:
            pub_date = meta("citation_publication_date")
            if pub_date:
                match = re.search(r"(20\d{2}|19\d{2})", pub_date)
                if match:
                    year = match.group(1)
        if year:
            metadata["year"] = year

        volume = meta("citation_volume")
        if volume:
            metadata["volume"] = volume

        issue = meta("citation_issue")
        if issue:
            metadata["issue"] = issue

        first_page = meta("citation_firstpage")
        last_page = meta("citation_lastpage")
        if first_page and last_page:
            metadata["pages"] = f"{first_page}-{last_page}"
        elif first_page:
            metadata["pages"] = first_page

        return metadata

    @staticmethod
    def _apply(entry: ReferenceEntry, metadata: Dict[str, object]) -> ReferenceEntry:
        if not metadata:
            return entry

        if metadata.get("authors") and not entry.authors:
            entry.authors = list(metadata["authors"])
        for field in ["title", "journal", "year", "volume", "issue", "pages", "doi"]:
            value = metadata.get(field)
            if value and getattr(entry, field) in (None, ""):
                setattr(entry, field, value)  # type: ignore[arg-type]
        return entry


__all__ = ["WebPageMetadataProvider"]
