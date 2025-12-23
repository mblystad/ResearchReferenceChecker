"""Formatting utilities for references."""
from __future__ import annotations

from .models import ReferenceEntry


class ReferenceFormatter:
    """Format references into target styles.

    This module intentionally avoids modifying manuscript body text, focusing solely on
    rendering reference entries using the available structured metadata.
    """

    SUPPORTED_STYLES = {"apa", "vancouver", "ieee", "harvard", "chicago"}

    def format(self, entry: ReferenceEntry, style: str = "apa") -> str:
        style_key = style.lower().strip()
        if style_key not in self.SUPPORTED_STYLES:
            style_key = "apa"
        formatter = getattr(self, f"format_{style_key}")
        return formatter(entry)

    def format_apa(self, entry: ReferenceEntry) -> str:
        authors = self._format_authors(entry)
        year = f"({entry.year})" if entry.year else None
        title = entry.title
        venue = self._venue(entry)
        details = self._format_volume_issue_pages(entry, sep=", ")
        publisher = entry.publisher
        locator = self._locator(entry)
        components = [comp for comp in [authors, year, title, venue, details, publisher, locator] if comp]
        return ". ".join(components)

    def format_vancouver(self, entry: ReferenceEntry) -> str:
        authors = self._format_authors(entry)
        title = entry.title
        venue = self._venue(entry) or entry.publisher
        year = entry.year
        volume = entry.volume
        issue = entry.issue
        pages = entry.pages
        locator = self._locator(entry)
        trailing = []
        if year:
            trailing.append(year)
        if volume:
            vol_issue = volume
            if issue:
                vol_issue = f"{vol_issue}({issue})"
            trailing.append(vol_issue)
        if pages:
            trailing.append(pages)
        core = ";".join(trailing) if trailing else None
        components = [comp for comp in [authors, title, venue, core, locator] if comp]
        return ". ".join(components)

    def format_ieee(self, entry: ReferenceEntry) -> str:
        authors = self._format_authors(entry)
        title = f"\"{entry.title}\"" if entry.title else None
        venue = self._venue(entry) or entry.publisher
        pieces = []
        if entry.volume:
            pieces.append(f"vol. {entry.volume}")
        if entry.issue:
            pieces.append(f"no. {entry.issue}")
        if entry.pages:
            pieces.append(f"pp. {entry.pages}")
        if entry.year:
            pieces.append(entry.year)
        details = ", ".join(pieces) if pieces else None
        locator = self._locator(entry)
        components = [comp for comp in [authors, title, venue, details, locator] if comp]
        return ", ".join(components)

    def format_harvard(self, entry: ReferenceEntry) -> str:
        authors = self._format_authors(entry)
        year = entry.year
        title = entry.title
        venue = self._venue(entry) or entry.publisher
        details = self._format_volume_issue_pages(entry, sep=", ")
        locator = self._locator(entry)
        components = [comp for comp in [authors, year, title, venue, details, locator] if comp]
        return ", ".join(components)

    def format_chicago(self, entry: ReferenceEntry) -> str:
        authors = self._format_authors(entry)
        title = f"\"{entry.title}\"" if entry.title else None
        venue = self._venue(entry) or entry.publisher
        year = entry.year
        details = self._format_volume_issue_pages(entry, sep=", ")
        core = []
        if venue:
            core.append(venue)
        if details:
            core.append(details)
        if year:
            core.append(f"({year})")
        core_text = " ".join(core) if core else None
        locator = self._locator(entry)
        components = [comp for comp in [authors, title, core_text, locator] if comp]
        return ". ".join(components)

    @staticmethod
    def _format_authors(entry: ReferenceEntry) -> str | None:
        return "; ".join(entry.authors) if entry.authors else None

    @staticmethod
    def _format_volume_issue_pages(entry: ReferenceEntry, sep: str = ", ") -> str | None:
        trailing = []
        if entry.volume:
            vol_issue = entry.volume
            if entry.issue:
                vol_issue = f"{vol_issue}({entry.issue})"
            trailing.append(vol_issue)
        if entry.pages:
            trailing.append(entry.pages)
        return sep.join(trailing) if trailing else None

    @staticmethod
    def _locator(entry: ReferenceEntry) -> str | None:
        if entry.doi:
            return f"https://doi.org/{entry.doi.lstrip('https://doi.org/')}"
        if entry.url:
            return entry.url
        return None

    @staticmethod
    def _venue(entry: ReferenceEntry) -> str | None:
        if entry.entry_type == "preprint" and entry.preprint_server:
            return entry.preprint_server
        return entry.journal or entry.book_title or entry.conference_name
