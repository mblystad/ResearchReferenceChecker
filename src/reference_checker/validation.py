"""Validation routines for references and citations."""
from __future__ import annotations

from typing import List

from .models import ReferenceEntry, ValidationIssue
from .link_checker import LinkVerifier


def validate_reference_completeness(reference: ReferenceEntry) -> List[ValidationIssue]:
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
