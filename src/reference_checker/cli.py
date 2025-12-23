"""Command line interface for processing manuscripts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from .app import ReferenceCheckerApp
from .crossref import CrossrefMetadataProvider, OnlineReferenceVerifier
from .link_checker import LinkVerifier
from .metadata import CompositeMetadataProvider
from .models import Citation, DocumentExtraction, ReferenceEntry, ValidationIssue
from .exporters import to_bibtex, to_endnote_xml, to_ris
from .report import render_report
from .web_metadata import WebPageMetadataProvider
from .predatory_db import PredatoryDbProvider


def _serialize_citation(citation: Citation) -> Dict[str, Any]:
    return {
        "text": citation.raw_text,
        "position": citation.position,
        "key": citation.normalized_key,
    }


def _serialize_reference(reference: ReferenceEntry) -> Dict[str, Any]:
    return {
        "index": reference.index_label,
        "raw_text": reference.raw_text,
        "authors": reference.authors,
        "title": reference.title,
        "journal": reference.journal,
        "book_title": reference.book_title,
        "conference_name": reference.conference_name,
        "publisher": reference.publisher,
        "preprint_server": reference.preprint_server,
        "dataset_name": reference.dataset_name,
        "year": reference.year,
        "volume": reference.volume,
        "issue": reference.issue,
        "pages": reference.pages,
        "doi": reference.doi,
        "url": reference.url,
        "entry_type": reference.entry_type,
    }


def _serialize_issues(issues: List[ValidationIssue]) -> List[Dict[str, Any]]:
    return [
        {
            "code": issue.code,
            "message": issue.message,
            "context": issue.context,
            "severity": issue.severity,
        }
        for issue in issues
    ]


def _build_result(extraction: DocumentExtraction, issues: List[ValidationIssue]) -> Dict[str, Any]:
    return {
        "citations": [_serialize_citation(c) for c in extraction.citations],
        "references": [_serialize_reference(r) for r in extraction.references],
        "issues": _serialize_issues(issues),
        "metadata": extraction.metadata,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate manuscript references")
    parser.add_argument("input", help="Path to DOCX, PDF, or text file to validate")
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Write structured validation results to a JSON file",
    )
    parser.add_argument(
        "--updated-docx",
        type=Path,
        help="Write an updated DOCX containing formatted references",
    )
    parser.add_argument(
        "--bibtex-output",
        type=Path,
        help="Write formatted references as BibTeX",
    )
    parser.add_argument(
        "--ris-output",
        type=Path,
        help="Write formatted references as RIS",
    )
    parser.add_argument(
        "--endnote-output",
        type=Path,
        help="Write formatted references as EndNote XML",
    )
    parser.add_argument(
        "--style",
        default="apa",
        choices=["apa", "vancouver", "ieee", "harvard", "chicago"],
        help="Reference style to use when formatting outputs",
    )
    parser.add_argument(
        "--check-links",
        action="store_true",
        help="Validate DOI/URL reachability (performs HTTP HEAD requests)",
    )
    parser.add_argument(
        "--web-metadata",
        action="store_true",
        help="Attempt to scrape public web pages (URL/DOI targets) to complete missing reference fields",
    )
    parser.add_argument(
        "--crossref-metadata",
        action="store_true",
        help="Query Crossref to fill missing reference metadata before validation",
    )
    parser.add_argument(
        "--verify-online",
        action="store_true",
        help="Compare references against Crossref to flag mismatched titles, authors, or years",
    )
    parser.add_argument(
        "--predatory-db",
        action="append",
        type=Path,
        help="Path to predatory journal/publisher CSV registry (can be repeated)",
    )
    parser.add_argument(
        "--no-predatory-db",
        action="store_true",
        help="Disable predatory journal screening",
    )
    args = parser.parse_args(argv)

    providers = []
    if args.web_metadata:
        providers.append(WebPageMetadataProvider())
    if args.crossref_metadata:
        providers.append(CrossrefMetadataProvider())
    if providers:
        metadata_provider = (
            providers[0] if len(providers) == 1 else CompositeMetadataProvider(providers)
        )
    else:
        metadata_provider = None
    online_verifier = OnlineReferenceVerifier() if args.verify_online else None
    predatory_provider = None
    enable_predatory_db = not args.no_predatory_db
    if args.predatory_db and enable_predatory_db:
        predatory_provider = PredatoryDbProvider.from_csv_paths(args.predatory_db)
    checker = ReferenceCheckerApp(
        metadata_provider=metadata_provider,
        link_verifier=LinkVerifier(),
        online_verifier=online_verifier,
        reference_style=args.style,
        predatory_db=predatory_provider,
        enable_predatory_db=enable_predatory_db,
    )
    input_path = Path(args.input)

    extraction, issues = checker.process_file(
        input_path, check_links=args.check_links, verify_online=args.verify_online
    )

    report = render_report(issues, extraction=extraction)
    print(report)

    if args.json_output:
        result = _build_result(extraction, issues)
        args.json_output.write_text(json.dumps(result, indent=2))

    if args.updated_docx:
        updated_bytes = checker.build_updated_docx(extraction, issues)
        args.updated_docx.write_bytes(updated_bytes)

    if args.bibtex_output:
        args.bibtex_output.write_text(to_bibtex(extraction.references))

    if args.ris_output:
        args.ris_output.write_text(to_ris(extraction.references))

    if args.endnote_output:
        args.endnote_output.write_text(to_endnote_xml(extraction.references))

    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
