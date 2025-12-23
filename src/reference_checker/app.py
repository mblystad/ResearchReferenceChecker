"""High-level orchestrator for reference validation workflows."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape
import zipfile

from .citation_extractor import CitationExtractor
from .formatter import ReferenceFormatter
from .matcher import CitationMatcher
from .link_checker import LinkVerifier
from .metadata import MetadataProvider
from .crossref import OnlineReferenceVerifier
from .models import Citation, DocumentExtraction, ReferenceEntry, ValidationIssue
from .parsers import DocumentParser
from .reference_parser import ReferenceListParser
from .report import render_report
from .predatory_db import PredatoryDbProvider
from .reference_types import classify_reference
from .validation import (
    validate_broken_citation_markers,
    validate_duplicate_references,
    validate_reference_completeness,
    validate_reference_links,
)


class ReferenceCheckerApp:
    """Coordinates parsing, validation, and export of references."""

    def __init__(
        self,
        metadata_provider: MetadataProvider | None = None,
        link_verifier: LinkVerifier | None = None,
        online_verifier: OnlineReferenceVerifier | None = None,
        reference_style: str = "apa",
        predatory_db: PredatoryDbProvider | None = None,
        enable_predatory_db: bool = True,
    ):
        self.parser = DocumentParser()
        self.citation_extractor = CitationExtractor()
        self.reference_parser = ReferenceListParser()
        self.matcher = CitationMatcher()
        self.formatter = ReferenceFormatter()
        self.metadata_provider = metadata_provider
        self.link_verifier = link_verifier
        self.online_verifier = online_verifier
        self.reference_style = reference_style
        if enable_predatory_db:
            self.predatory_db = predatory_db or PredatoryDbProvider.load_default()
        else:
            self.predatory_db = None

    @staticmethod
    def _issues_by_reference(
        issues: List[ValidationIssue], references: List[ReferenceEntry]
    ) -> Dict[int, List[str]]:
        """Group validation messages by reference index based on raw text context."""

        grouped: Dict[int, List[str]] = {}
        for issue in issues:
            if not issue.context:
                continue
            for idx, ref in enumerate(references):
                if issue.context == ref.raw_text:
                    grouped.setdefault(idx, []).append(issue.message)
                    break
        return grouped

    def process_text(
        self, text: str, check_links: bool = False, verify_online: bool = False
    ) -> Tuple[DocumentExtraction, List[ValidationIssue]]:
        body, refs_text = self.parser.split_sections(text)
        citations = self.citation_extractor.extract(body)
        references = self.reference_parser.parse(refs_text)
        if self.metadata_provider:
            references = [self.metadata_provider.enrich(ref) for ref in references]
        for ref in references:
            ref.entry_type = classify_reference(ref)
        matches, match_issues = self.matcher.match(citations, references)

        validation_issues: List[ValidationIssue] = list(match_issues)
        validation_issues.extend(validate_broken_citation_markers(body))
        validation_issues.extend(validate_duplicate_references(references))
        link_verifier = self.link_verifier if check_links else None
        online_verifier = self.online_verifier if verify_online else None
        for ref in references:
            validation_issues.extend(
                validate_reference_completeness(ref, style=self.reference_style)
            )
            if self.predatory_db:
                validation_issues.extend(self.predatory_db.check_reference(ref))
            if check_links:
                if link_verifier is None:
                    link_verifier = LinkVerifier()
                validation_issues.extend(validate_reference_links(ref, link_verifier))
            if verify_online:
                if online_verifier is None:
                    online_verifier = OnlineReferenceVerifier()
                validation_issues.extend(online_verifier.verify(ref))

        extraction = DocumentExtraction(
            body_text=body,
            references_text=refs_text,
            citations=citations,
            references=references,
            metadata={"matched": len(matches)},
        )
        return extraction, validation_issues

    def process_docx(
        self, file_path: str | Path, check_links: bool = False, verify_online: bool = False
    ) -> Tuple[DocumentExtraction, List[ValidationIssue]]:
        """Convenience wrapper to parse and validate DOCX manuscripts."""

        text = self.parser.load_docx_text(file_path)
        return self.process_text(text, check_links=check_links, verify_online=verify_online)

    def process_file(
        self, file_path: str | Path, check_links: bool = False, verify_online: bool = False
    ) -> Tuple[DocumentExtraction, List[ValidationIssue]]:
        """Parse supported manuscript files (DOCX, PDF, or text)."""
        text = self.parser.load_text(file_path)
        return self.process_text(text, check_links=check_links, verify_online=verify_online)

    def validation_report(self, text: str) -> str:
        _, issues = self.process_text(text)
        return render_report(issues)

    def user_report_for_docx(
        self, file_path: str | Path, check_links: bool = False, verify_online: bool = False
    ) -> str:
        """Generate a user-friendly report for a DOCX manuscript."""

        extraction, issues = self.process_docx(
            file_path, check_links=check_links, verify_online=verify_online
        )
        return render_report(issues, extraction=extraction)

    def format_references(self, references: List[ReferenceEntry]) -> List[str]:
        return [self.formatter.format(ref, self.reference_style) for ref in references]

    def build_updated_docx(
        self, extraction: DocumentExtraction, issues: List[ValidationIssue]
    ) -> bytes:
        """Create a DOCX copy containing original text and a refreshed reference list."""

        paragraphs = [line for line in extraction.body_text.splitlines() if line]
        paragraphs.append("References")

        missing_issues = [issue for issue in issues if _is_missing_detail(issue)]
        issues_by_ref = self._issues_by_reference(missing_issues, extraction.references)

        for idx, ref in enumerate(extraction.references, start=1):
            formatted = self.formatter.format(ref, self.reference_style)
            paragraphs.append(f"{idx}. {formatted}")

            missing = issues_by_ref.get(idx - 1)
            if missing:
                paragraphs.append("Missing details: " + "; ".join(sorted(set(missing))))

        return self._build_minimal_docx(paragraphs)

    @staticmethod
    def _build_minimal_docx(paragraphs: List[str]) -> bytes:
        """Create a minimal DOCX file containing the provided paragraphs."""

        document_xml_parts = [
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
            "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">",
            "<w:body>",
        ]
        for para in paragraphs:
            document_xml_parts.append(
                "<w:p><w:r><w:t>{}</w:t></w:r></w:p>".format(escape(para))
            )
        document_xml_parts.append("</w:body></w:document>")
        document_xml = "".join(document_xml_parts)

        content_types = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
    <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
    <Default Extension=\"xml\" ContentType=\"application/xml\"/>
    <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>
</Types>"""

        rels = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
    <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>
</Relationships>"""

        word_rels = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"></Relationships>"""

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, mode="w") as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("_rels/.rels", rels)
            archive.writestr("word/_rels/document.xml.rels", word_rels)
            archive.writestr("word/document.xml", document_xml)
        return buffer.getvalue()


def _is_missing_detail(issue: ValidationIssue) -> bool:
    code = issue.code.lower()
    return code.startswith("missing-") or code.startswith("apa-") or "missing-" in code
