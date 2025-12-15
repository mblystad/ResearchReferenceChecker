"""Formatting utilities for references."""
from __future__ import annotations

from .models import ReferenceEntry


class ReferenceFormatter:
    """Format references into target styles.

    This module intentionally avoids modifying manuscript body text, focusing solely on
    rendering reference entries using the available structured metadata.
    """

    def format_apa(self, entry: ReferenceEntry) -> str:
        authors = "; ".join(entry.authors) if entry.authors else ""
        components = [comp for comp in [authors, f"({entry.year})" if entry.year else None, entry.title, entry.journal] if comp]
        trailing = []
        if entry.volume:
            vol_issue = entry.volume
            if entry.issue:
                vol_issue = f"{vol_issue}({entry.issue})"
            trailing.append(vol_issue)
        if entry.pages:
            trailing.append(entry.pages)
        if trailing:
            components.append(", ".join(trailing))
        if entry.doi:
            components.append(f"https://doi.org/{entry.doi.lstrip('https://doi.org/')}")
        elif entry.url:
            components.append(entry.url)
        return ". ".join(components)
