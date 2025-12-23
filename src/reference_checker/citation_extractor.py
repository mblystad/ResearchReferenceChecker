"""Utilities for detecting in-text citations."""
from __future__ import annotations

import re
from typing import Iterable, List

from .models import Citation


class CitationExtractor:
    """Extract citations using lightweight heuristics."""

    NUMERIC_PATTERN = re.compile(r"\[(?P<labels>[\d,\s\-]+)\]")
    PAREN_PATTERN = re.compile(
        r"\((?P<author>[A-Z][A-Za-z\-]+)(?:\s+et al\.)?,?\s*(?P<year>\d{4})\)"
    )

    def extract(self, text: str) -> List[Citation]:
        citations: List[Citation] = []
        for match in self.NUMERIC_PATTERN.finditer(text):
            labels = match.group("labels")
            for label in self._expand_numeric_labels(labels):
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

    @staticmethod
    def _expand_numeric_labels(label_text: str) -> List[str]:
        labels: List[str] = []
        for part in [seg.strip() for seg in label_text.split(",") if seg.strip()]:
            if "-" in part:
                start, end = (seg.strip() for seg in part.split("-", 1))
                if start.isdigit() and end.isdigit():
                    labels.extend([str(i) for i in range(int(start), int(end) + 1)])
                else:
                    labels.append(part)
            else:
                labels.append(part)
        return labels

    def extract_keys(self, citations: Iterable[Citation]) -> List[str]:
        return [c.normalized_key for c in citations]
