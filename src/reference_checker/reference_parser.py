"""Parsers for reference list entries."""
from __future__ import annotations

import re
from typing import List

from .models import ReferenceEntry


class ReferenceListParser:
    """Parses raw reference list text into structured entries."""

    DOI_PATTERN = re.compile(r"10\.\d{4,9}/[\S]+", re.IGNORECASE)
    URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)

    def parse(self, text: str) -> List[ReferenceEntry]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        entries: List[ReferenceEntry] = []
        for line in lines:
            index_label, content = self._split_index(line)
            entry = ReferenceEntry(
                raw_text=line,
                index_label=index_label,
                authors=self._extract_authors(content),
                title=self._extract_title(content),
                year=self._extract_year(content),
                doi=self._extract_doi(content),
                url=self._extract_url(content),
            )
            entries.append(entry)
        return entries

    def _split_index(self, line: str) -> tuple[str | None, str]:
        numeric_prefix = re.match(r"^(\[?\d+\]?\.?)\s*(.+)$", line)
        if numeric_prefix:
            return numeric_prefix.group(1).strip("[]."), numeric_prefix.group(2).strip()
        return None, line

    def _extract_authors(self, content: str) -> List[str]:
        if not content:
            return []
        author_part = content.split(".")[0]
        parts = [a.strip() for a in author_part.split(";") if a.strip()]
        if not parts:
            parts = [a.strip() for a in author_part.split(",") if a.strip()]
        return parts

    def _extract_year(self, content: str) -> str | None:
        match = re.search(r"(19|20)\d{2}", content)
        return match.group(0) if match else None

    def _extract_title(self, content: str) -> str | None:
        segments = [seg.strip() for seg in content.split(".") if seg.strip()]
        if len(segments) > 1:
            return segments[1]
        return None

    def _extract_doi(self, content: str) -> str | None:
        match = self.DOI_PATTERN.search(content)
        if match:
            return match.group(0)
        return None

    def _extract_url(self, content: str) -> str | None:
        match = self.URL_PATTERN.search(content)
        if match:
            return match.group(0)
        return None
