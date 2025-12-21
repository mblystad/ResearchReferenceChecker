"""Exporters for structured reference data."""
from __future__ import annotations

import json
from typing import List

from .models import ReferenceEntry


def to_json(references: List[ReferenceEntry]) -> str:
    return json.dumps([ref.__dict__ for ref in references], indent=2)


def to_bibtex(references: List[ReferenceEntry]) -> str:
    entries = []
    for idx, ref in enumerate(references, start=1):
        key = ref.formatted_key() or f"ref{idx}"
        lines = [f"@article{{{key},"]
        if ref.authors:
            lines.append(f"  author = {{{' and '.join(ref.authors)}}},")
        if ref.title:
            lines.append(f"  title = {{{ref.title}}},")
        if ref.journal:
            lines.append(f"  journal = {{{ref.journal}}},")
        if ref.year:
            lines.append(f"  year = {{{ref.year}}},")
        if ref.volume:
            lines.append(f"  volume = {{{ref.volume}}},")
        if ref.issue:
            lines.append(f"  number = {{{ref.issue}}},")
        if ref.pages:
            lines.append(f"  pages = {{{ref.pages}}},")
        if ref.doi:
            lines.append(f"  doi = {{{ref.doi}}},")
        if ref.url:
            lines.append(f"  url = {{{ref.url}}},")
        lines.append("}")
        entries.append("\n".join(lines))
    return "\n\n".join(entries)
