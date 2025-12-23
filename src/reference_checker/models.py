"""Data models for reference validation workflows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Citation:
    """Represents an in-text citation marker."""

    raw_text: str
    position: int
    normalized_key: str


@dataclass
class ReferenceEntry:
    """Represents a reference list entry."""

    raw_text: str
    index_label: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    title: Optional[str] = None
    journal: Optional[str] = None
    book_title: Optional[str] = None
    conference_name: Optional[str] = None
    publisher: Optional[str] = None
    preprint_server: Optional[str] = None
    dataset_name: Optional[str] = None
    year: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    entry_type: Optional[str] = None

    def formatted_key(self) -> str:
        """Return a normalized key for matching purposes."""
        if self.index_label:
            return self.index_label.strip().lower()
        if self.authors and self.year:
            lead = self.authors[0].split(",")[0].strip().lower()
            return f"{lead}{self.year}"
        return self.raw_text.strip().lower()


@dataclass
class ValidationIssue:
    """Represents a validation finding."""

    code: str
    message: str
    context: Optional[str] = None
    severity: str = "warning"


@dataclass
class DocumentExtraction:
    """Container for parsed document components."""

    body_text: str
    references_text: str
    citations: List[Citation]
    references: List[ReferenceEntry]
    metadata: Dict[str, str] = field(default_factory=dict)
