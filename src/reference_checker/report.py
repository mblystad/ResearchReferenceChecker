"""Validation reporting utilities."""
from __future__ import annotations

from typing import List

from .models import DocumentExtraction, ValidationIssue


def render_report(issues: List[ValidationIssue], extraction: DocumentExtraction | None = None) -> str:
    """Return a human-readable report summarizing validation findings."""

    header_lines = ["Reference Validation Report"]
    if extraction:
        unique_citations = extraction.metadata.get("unique_citations")
        citation_mentions = extraction.metadata.get("citation_mentions")
        if isinstance(unique_citations, int):
            if isinstance(citation_mentions, int) and citation_mentions != unique_citations:
                header_lines.append(
                    f"Citations detected: {unique_citations} ({citation_mentions} mentions)"
                )
            else:
                header_lines.append(f"Citations detected: {unique_citations}")
        else:
            header_lines.append(f"Citations detected: {len(extraction.citations)}")
        header_lines.append(f"Reference entries: {len(extraction.references)}")
        matched = extraction.metadata.get("matched")
        if matched is not None:
            header_lines.append(f"Matched pairs: {matched}")

    if not issues:
        header_lines.append("No reference issues detected.")
        return "\n".join(header_lines)

    lines = header_lines + ["Issues:"]
    for issue in issues:
        line = f"[{issue.severity.upper()}] {issue.code}: {issue.message}"
        if issue.context:
            line += f" -> {issue.context}"
        lines.append(line)
    return "\n".join(lines)
