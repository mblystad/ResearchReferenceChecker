"""Reference type classification heuristics."""
from __future__ import annotations

from dataclasses import dataclass

from .models import ReferenceEntry


@dataclass(frozen=True)
class ReferenceType:
    key: str
    label: str


REFERENCE_TYPES = {
    "journal": ReferenceType("journal", "Journal Article"),
    "book": ReferenceType("book", "Book"),
    "chapter": ReferenceType("chapter", "Book Chapter"),
    "conference": ReferenceType("conference", "Conference Paper"),
    "preprint": ReferenceType("preprint", "Preprint"),
    "website": ReferenceType("website", "Website"),
    "dataset": ReferenceType("dataset", "Dataset"),
    "unknown": ReferenceType("unknown", "Unknown"),
}


_CROSSREF_TYPE_MAP = {
    "journal-article": "journal",
    "article-journal": "journal",
    "book": "book",
    "book-chapter": "chapter",
    "proceedings-article": "conference",
    "posted-content": "preprint",
    "dataset": "dataset",
    "report": "book",
    "standard": "book",
    "proceedings": "conference",
}


def classify_reference(entry: ReferenceEntry) -> str:
    """Return a normalized reference type key for the entry."""
    if entry.entry_type:
        mapped = _CROSSREF_TYPE_MAP.get(entry.entry_type.lower())
        if mapped:
            return mapped

    raw = (entry.raw_text or "").lower()
    title = (entry.title or "").lower()
    url = (entry.url or "").lower()

    if _looks_like_dataset(raw, title, url):
        return "dataset"
    if _looks_like_preprint(raw, title, url):
        return "preprint"
    if _looks_like_conference(raw):
        return "conference"
    if _looks_like_book_chapter(raw):
        return "chapter"
    if _looks_like_book(raw):
        return "book"
    if entry.journal:
        return "journal"
    if entry.url and not entry.journal:
        return "website"
    return "unknown"


def _looks_like_dataset(raw: str, title: str, url: str) -> bool:
    dataset_terms = ["dataset", "data set", "data repository", "supplementary data"]
    repo_terms = ["zenodo", "figshare", "dryad", "osf", "kaggle", "dataverse"]
    return any(term in raw for term in dataset_terms) or any(term in url for term in repo_terms) or any(term in title for term in dataset_terms)


def _looks_like_preprint(raw: str, title: str, url: str) -> bool:
    preprint_terms = ["preprint", "arxiv", "biorxiv", "medrxiv", "ssrn", "research square"]
    return any(term in raw for term in preprint_terms) or any(term in url for term in preprint_terms) or any(term in title for term in preprint_terms)


def _looks_like_conference(raw: str) -> bool:
    conf_terms = ["proceedings", "conference", "symposium", "workshop"]
    return any(term in raw for term in conf_terms)


def _looks_like_book_chapter(raw: str) -> bool:
    return "chapter" in raw and "in:" in raw


def _looks_like_book(raw: str) -> bool:
    pub_terms = ["press", "publishing", "publisher", "edition"]
    return any(term in raw for term in pub_terms)


def label_for_type(type_key: str | None) -> str:
    if not type_key:
        return REFERENCE_TYPES["unknown"].label
    ref_type = REFERENCE_TYPES.get(type_key, REFERENCE_TYPES["unknown"])
    return ref_type.label
