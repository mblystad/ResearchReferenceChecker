"""Logic for matching citations to reference list entries."""
from __future__ import annotations

from typing import Dict, List, Tuple

from .models import Citation, ReferenceEntry, ValidationIssue


class CitationMatcher:
    """Match in-text citations to reference entries using keys and labels."""

    def match(self, citations: List[Citation], references: List[ReferenceEntry]) -> Tuple[Dict[str, ReferenceEntry], List[ValidationIssue]]:
        ref_by_key: Dict[str, ReferenceEntry] = {ref.formatted_key(): ref for ref in references}
        issues: List[ValidationIssue] = []
        matches: Dict[str, ReferenceEntry] = {}

        for citation in citations:
            key = citation.normalized_key
            if key in ref_by_key:
                matches[key] = ref_by_key[key]
            else:
                issues.append(
                    ValidationIssue(
                        code="missing-reference",
                        message=f"No reference entry for citation {citation.raw_text}",
                        context=citation.raw_text,
                        severity="error",
                    )
                )

        referenced_keys = {ref.formatted_key() for ref in references}
        cited_keys = {c.normalized_key for c in citations}
        for orphan in referenced_keys - cited_keys:
            issues.append(
                ValidationIssue(
                    code="uncited-reference",
                    message="Reference not cited in text",
                    context=orphan,
                )
            )

        return matches, issues
