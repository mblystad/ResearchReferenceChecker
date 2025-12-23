"""Parsers for reference list entries."""
from __future__ import annotations

import re
from typing import List

from .models import ReferenceEntry
from .reference_types import classify_reference


class ReferenceListParser:
    """Parses raw reference list text into structured entries."""

    DOI_PATTERN = re.compile(r"10\.\d{4,9}/[\S]+", re.IGNORECASE)
    URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
    PAGE_PATTERN = re.compile(r"(\d+)\s*[-–]\s*(\d+)")
    VOLUME_ISSUE_PATTERN = re.compile(r"(\d+)\s*\((\d+)\)")
    CONFERENCE_PATTERN = re.compile(r"(proceedings of|conference on|conference|symposium|workshop)(.+)", re.IGNORECASE)
    PREPRINT_PATTERN = re.compile(r"\b(arxiv|biorxiv|medrxiv|ssrn|research square)\b", re.IGNORECASE)

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
                journal=self._extract_journal(content),
                year=self._extract_year(content),
                volume=self._extract_volume(content),
                issue=self._extract_issue(content),
                pages=self._extract_pages(content),
                doi=self._extract_doi(content),
                url=self._extract_url(content),
                publisher=self._extract_publisher(content),
                conference_name=self._extract_conference(content),
                preprint_server=self._extract_preprint_server(content),
            )
            if entry.title and self._looks_like_dataset(entry):
                entry.dataset_name = entry.title
            entry.entry_type = classify_reference(entry)
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
        return [self._normalize_author(part) for part in parts if part]

    def _extract_year(self, content: str) -> str | None:
        match = re.search(r"(19|20)\d{2}", content)
        return match.group(0) if match else None

    def _extract_title(self, content: str) -> str | None:
        segments = [seg.strip() for seg in content.split(".") if seg.strip()]
        if len(segments) > 1:
            return segments[1]
        return None

    def _extract_journal(self, content: str) -> str | None:
        segments = [seg.strip() for seg in content.split(".") if seg.strip()]
        if len(segments) < 3:
            return None
        title = self._extract_title(content)
        candidates = [seg for seg in segments if seg and seg != title]
        for seg in candidates[1:]:
            if self._extract_year(seg):
                break
            if seg.lower().startswith("available from"):
                break
            return seg
        return None

    def _extract_volume(self, content: str) -> str | None:
        match = self.VOLUME_ISSUE_PATTERN.search(content)
        if match:
            return match.group(1)
        match = re.search(r"(?:\bvol\.?\s*)(\d+)", content, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_issue(self, content: str) -> str | None:
        match = self.VOLUME_ISSUE_PATTERN.search(content)
        if match:
            return match.group(2)
        match = re.search(r"(?:\bno\.?\s*)(\d+)", content, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_pages(self, content: str) -> str | None:
        match = self.PAGE_PATTERN.search(content)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        match = re.search(r"(?:pp\.?\s*)(\d+[-–]\d+)", content, re.IGNORECASE)
        if match:
            return match.group(1)
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

    def _extract_publisher(self, content: str) -> str | None:
        match = re.search(r"\b([A-Z][A-Za-z&.\s]+)\s*(Press|Publishing|Publisher)\b", content)
        if match:
            return f"{match.group(1).strip()} {match.group(2)}"
        return None

    def _extract_conference(self, content: str) -> str | None:
        match = self.CONFERENCE_PATTERN.search(content)
        if match:
            return match.group(0).strip()
        return None

    def _extract_preprint_server(self, content: str) -> str | None:
        match = self.PREPRINT_PATTERN.search(content)
        if match:
            return match.group(1)
        return None

    def _normalize_author(self, author: str) -> str:
        author = author.strip()
        if "," in author:
            return author
        parts = author.split()
        if len(parts) >= 2:
            if parts[-1].endswith(".") and len(parts[-1]) <= 3:
                last = parts[0]
                first = " ".join(parts[1:])
            else:
                last = parts[-1]
                first = " ".join(parts[:-1])
            return f"{last}, {first}"
        return author

    def _looks_like_dataset(self, entry: ReferenceEntry) -> bool:
        content = entry.raw_text.lower()
        return "dataset" in content or "data set" in content
