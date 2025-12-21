"""Utilities for detecting in-text citations."""
from __future__ import annotations

import re
from typing import Iterable, List

from .models import Citation


class CitationExtractor:
    """Extract citations using lightweight heuristics."""

    NUMERIC_PATTERN = re.compile(r"\[(?P<label>\d+)\]")
    PAREN_PATTERN = re.compile(r"\((?P<author>[A-Z][A-Za-z\-]+)\s*(?P<year>\d{4})\)")

    def extract(self, text: str) -> List[Citation]:
        citations: List[Citation] = []
        for match in self.NUMERIC_PATTERN.finditer(text):
            label = match.group("label")
            citations.append(
                Citation(
                    raw_text=match.group(0),
                    position=match.start(),
                    normalized_key=label.lower(),
                )
            )
        for match in self.PAREN_PATTERN.finditer(text):
            key = f"{match.group('author').lower()}{match.group('year')}"
            citations.append(
                Citation(
                    raw_text=match.group(0),
                    position=match.start(),
                    normalized_key=key,
                )
            )
        return sorted(citations, key=lambda c: c.position)

    def extract_keys(self, citations: Iterable[Citation]) -> List[str]:
        return [c.normalized_key for c in citations]
