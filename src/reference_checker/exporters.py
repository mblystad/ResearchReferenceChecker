"""Exporters for structured reference data."""
from __future__ import annotations

import json
from typing import List

from .models import ReferenceEntry
from .reference_types import classify_reference


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


def to_ris(references: List[ReferenceEntry]) -> str:
    entries = []
    for ref in references:
        ref_type = classify_reference(ref)
        ty = _ris_type(ref_type)
        lines = [f"TY  - {ty}"]
        for author in ref.authors:
            lines.append(f"AU  - {author}")
        if ref.title:
            lines.append(f"TI  - {ref.title}")
        if ref.journal:
            lines.append(f"JO  - {ref.journal}")
        if ref.book_title:
            lines.append(f"T2  - {ref.book_title}")
        if ref.conference_name:
            lines.append(f"T2  - {ref.conference_name}")
        if ref.publisher:
            lines.append(f"PB  - {ref.publisher}")
        if ref.year:
            lines.append(f"PY  - {ref.year}")
        if ref.volume:
            lines.append(f"VL  - {ref.volume}")
        if ref.issue:
            lines.append(f"IS  - {ref.issue}")
        if ref.pages:
            start, end = _split_pages(ref.pages)
            if start:
                lines.append(f"SP  - {start}")
            if end:
                lines.append(f"EP  - {end}")
        if ref.doi:
            lines.append(f"DO  - {ref.doi}")
        if ref.url:
            lines.append(f"UR  - {ref.url}")
        lines.append("ER  - ")
        entries.append("\n".join(lines))
    return "\n\n".join(entries)


def to_endnote_xml(references: List[ReferenceEntry]) -> str:
    records = []
    for ref in references:
        ref_type = classify_reference(ref)
        record = [
            "<record>",
            f"<ref-type name=\"{_endnote_type(ref_type)}\"/>",
            "<titles>",
        ]
        if ref.title:
            record.append(f"<title>{_xml_escape(ref.title)}</title>")
        if ref.journal:
            record.append(f"<secondary-title>{_xml_escape(ref.journal)}</secondary-title>")
        if ref.book_title:
            record.append(f"<secondary-title>{_xml_escape(ref.book_title)}</secondary-title>")
        if ref.conference_name:
            record.append(
                f"<tertiary-title>{_xml_escape(ref.conference_name)}</tertiary-title>"
            )
        record.append("</titles>")
        if ref.authors:
            record.append("<contributors><authors>")
            for author in ref.authors:
                record.append(f"<author>{_xml_escape(author)}</author>")
            record.append("</authors></contributors>")
        if ref.year:
            record.append(f"<dates><year>{_xml_escape(ref.year)}</year></dates>")
        if ref.publisher:
            record.append(f"<publisher>{_xml_escape(ref.publisher)}</publisher>")
        if ref.volume:
            record.append(f"<volume>{_xml_escape(ref.volume)}</volume>")
        if ref.issue:
            record.append(f"<number>{_xml_escape(ref.issue)}</number>")
        if ref.pages:
            record.append(f"<pages>{_xml_escape(ref.pages)}</pages>")
        if ref.doi:
            record.append(f"<electronic-resource-num>{_xml_escape(ref.doi)}</electronic-resource-num>")
        if ref.url:
            record.append(f"<url>{_xml_escape(ref.url)}</url>")
        record.append("</record>")
        records.append("".join(record))
    return f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><records>{''.join(records)}</records>"


def _split_pages(pages: str) -> tuple[str | None, str | None]:
    if "-" in pages:
        start, end = pages.split("-", 1)
        return start.strip(), end.strip()
    return pages.strip(), None


def _ris_type(type_key: str) -> str:
    return {
        "journal": "JOUR",
        "book": "BOOK",
        "chapter": "CHAP",
        "conference": "CONF",
        "dataset": "DATA",
        "preprint": "GEN",
        "website": "ELEC",
    }.get(type_key, "GEN")


def _endnote_type(type_key: str) -> str:
    return {
        "journal": "Journal Article",
        "book": "Book",
        "chapter": "Book Section",
        "conference": "Conference Paper",
        "dataset": "Dataset",
        "preprint": "Preprint",
        "website": "Web Page",
    }.get(type_key, "Generic")


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&apos;")
    )
