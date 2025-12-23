"""Validation routines for references and citations."""
from __future__ import annotations

from typing import List
import re

from .models import ReferenceEntry, ValidationIssue
from .link_checker import LinkVerifier
from .reference_types import label_for_type


def validate_reference_completeness(
    reference: ReferenceEntry, style: str = "apa"
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    if not reference.authors:
        issues.append(
            ValidationIssue(
                code="missing-authors",
                message="Reference entry missing authors",
                context=reference.raw_text,
            )
        )
    if not reference.title:
        issues.append(
            ValidationIssue(
                code="missing-title",
                message="Reference entry missing title",
                context=reference.raw_text,
            )
        )
    if not reference.year:
        issues.append(
            ValidationIssue(
                code="missing-year",
                message="Reference entry missing year",
                context=reference.raw_text,
            )
        )
    if not (reference.doi or reference.url):
        issues.append(
            ValidationIssue(
                code="missing-locator",
                message="Reference entry missing DOI or URL",
                context=reference.raw_text,
            )
        )
    issues.extend(_validate_type_specific_fields(reference))
    style_key = style.strip().lower()
    if style_key == "apa":
        issues.extend(_validate_apa_fields(reference))
    elif style_key == "ama":
        issues.extend(_validate_ama_fields(reference))
    return issues


def _validate_type_specific_fields(reference: ReferenceEntry) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    ref_type = (reference.entry_type or "unknown").lower()
    type_label = label_for_type(ref_type)

    def add_issue(code_suffix: str, message: str) -> None:
        issues.append(
            ValidationIssue(
                code=f"{ref_type}-{code_suffix}",
                message=f"{type_label}: {message}",
                context=reference.raw_text,
            )
        )

    if ref_type == "journal" and not reference.journal:
        add_issue("missing-journal", "missing journal or venue")
    if ref_type in {"book", "chapter"} and not reference.publisher:
        add_issue("missing-publisher", "missing publisher")
    if ref_type == "chapter" and not reference.book_title:
        add_issue("missing-book-title", "missing book title")
    if ref_type == "conference" and not (reference.conference_name or reference.journal):
        add_issue("missing-conference", "missing conference or proceedings name")
    if ref_type == "preprint" and not reference.preprint_server:
        add_issue("missing-preprint-server", "missing preprint server")
    if ref_type == "dataset" and not (reference.dataset_name or reference.title):
        add_issue("missing-dataset-name", "missing dataset title")
    if ref_type == "website" and not reference.url:
        add_issue("missing-url", "missing URL")
    return issues


def _validate_apa_fields(reference: ReferenceEntry) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    ref_type = (reference.entry_type or "unknown").lower()
    type_label = label_for_type(ref_type)

    def add_issue(code_suffix: str, message: str) -> None:
        issues.append(
            ValidationIssue(
                code=f"apa-{ref_type}-{code_suffix}",
                message=f"{type_label} (APA): {message}",
                context=reference.raw_text,
            )
        )

    if ref_type == "journal":
        if not reference.volume:
            add_issue("missing-volume", "missing volume number")
        if not reference.issue:
            add_issue("missing-issue", "missing issue number")
        if not reference.pages:
            add_issue("missing-pages", "missing page range")
    if ref_type in {"chapter", "conference"} and not reference.pages:
        add_issue("missing-pages", "missing page range")
    return issues


def _validate_ama_fields(reference: ReferenceEntry) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    ref_type = (reference.entry_type or "unknown").lower()
    type_label = label_for_type(ref_type)

    def add_issue(code_suffix: str, message: str) -> None:
        issues.append(
            ValidationIssue(
                code=f"ama-{ref_type}-{code_suffix}",
                message=f"{type_label} (AMA): {message}",
                context=reference.raw_text,
            )
        )

    if ref_type == "journal":
        if not reference.volume:
            add_issue("missing-volume", "missing volume number")
        if not reference.issue:
            add_issue("missing-issue", "missing issue number")
        if not reference.pages:
            add_issue("missing-pages", "missing page range")
    if ref_type in {"chapter", "conference"} and not reference.pages:
        add_issue("missing-pages", "missing page range")
    if ref_type == "website" and not reference.url:
        add_issue("missing-url", "missing URL")
    return issues


def validate_reference_links(
    reference: ReferenceEntry, verifier: LinkVerifier | None
) -> List[ValidationIssue]:
    """Validate DOI/URL reachability when a verifier is supplied."""

    if verifier is None:
        return []

    targets: List[tuple[str, str]] = []
    if reference.doi:
        doi_url = reference.doi
        if not doi_url.startswith("http"):
            doi_url = f"https://doi.org/{reference.doi}"
        targets.append(("doi", doi_url))
    if reference.url:
        targets.append(("url", reference.url))

    issues: List[ValidationIssue] = []
    seen = set()
    for kind, url in targets:
        if url in seen:
            continue
        seen.add(url)
        result = verifier.check(url)
        if not result.reachable:
            detail = f"{kind.upper()} unreachable"
            if result.status_code:
                detail += f" (status {result.status_code})"
            elif result.error:
                detail += f" ({result.error})"
            issues.append(
                ValidationIssue(
                    code=f"{kind}-unreachable",
                    message=detail,
                    context=reference.raw_text,
                    severity="error",
                )
            )
    return issues


def validate_duplicate_references(references: List[ReferenceEntry]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_keys: dict[str, ReferenceEntry] = {}
    seen_dois: dict[str, ReferenceEntry] = {}

    for ref in references:
        key = ref.formatted_key()
        if key in seen_keys:
            issues.append(
                ValidationIssue(
                    code="duplicate-reference",
                    message="Duplicate reference detected",
                    context=ref.raw_text,
                )
            )
        else:
            seen_keys[key] = ref

        if ref.doi:
            doi_key = ref.doi.strip().lower()
            if doi_key in seen_dois:
                issues.append(
                    ValidationIssue(
                        code="duplicate-doi",
                        message="Duplicate DOI detected",
                        context=ref.raw_text,
                    )
                )
            else:
                seen_dois[doi_key] = ref

    return issues


def validate_broken_citation_markers(text: str) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    open_brackets = text.count("[")
    close_brackets = text.count("]")
    if open_brackets != close_brackets:
        issues.append(
            ValidationIssue(
                code="broken-citation-brackets",
                message="Unbalanced citation brackets detected",
                context="[]",
            )
        )

    open_parens = text.count("(")
    close_parens = text.count(")")
    if open_parens != close_parens:
        issues.append(
            ValidationIssue(
                code="broken-citation-parentheses",
                message="Unbalanced citation parentheses detected",
                context="()",
            )
        )

    dangling = re.search(r"\[(?!\d)", text)
    if dangling:
        issues.append(
            ValidationIssue(
                code="broken-citation-marker",
                message="Citation marker contains non-numeric label",
                context=dangling.group(0),
            )
        )
    return issues
