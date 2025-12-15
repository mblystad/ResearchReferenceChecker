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
from .models import Citation, DocumentExtraction, ReferenceEntry, ValidationIssue
from .parsers import DocumentParser
from .reference_parser import ReferenceListParser
from .report import render_report
from .validation import validate_reference_completeness, validate_reference_links


class ReferenceCheckerApp:
    """Coordinates parsing, validation, and export of references."""

    def __init__(
        self,
        metadata_provider: MetadataProvider | None = None,
        link_verifier: LinkVerifier | None = None,
    ):
        self.parser = DocumentParser()
        self.citation_extractor = CitationExtractor()
        self.reference_parser = ReferenceListParser()
        self.matcher = CitationMatcher()
        self.formatter = ReferenceFormatter()
        self.metadata_provider = metadata_provider
        self.link_verifier = link_verifier

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
        self, text: str, check_links: bool = False
    ) -> Tuple[DocumentExtraction, List[ValidationIssue]]:
        body, refs_text = self.parser.split_sections(text)
        citations = self.citation_extractor.extract(body)
        references = self.reference_parser.parse(refs_text)
        if self.metadata_provider:
            references = [self.metadata_provider.enrich(ref) for ref in references]
        matches, match_issues = self.matcher.match(citations, references)

        validation_issues: List[ValidationIssue] = list(match_issues)
        for ref in references:
            validation_issues.extend(validate_reference_completeness(ref))
            if check_links:
                verifier = self.link_verifier or LinkVerifier()
                validation_issues.extend(validate_reference_links(ref, verifier))

        extraction = DocumentExtraction(
            body_text=body,
            references_text=refs_text,
            citations=citations,
            references=references,
            metadata={"matched": len(matches)},
        )
        return extraction, validation_issues

    def process_docx(
        self, file_path: str | Path, check_links: bool = False
    ) -> Tuple[DocumentExtraction, List[ValidationIssue]]:
        """Convenience wrapper to parse and validate DOCX manuscripts."""

        text = self.parser.load_docx_text(file_path)
        return self.process_text(text, check_links=check_links)

    def validation_report(self, text: str) -> str:
        _, issues = self.process_text(text)
        return render_report(issues)

    def user_report_for_docx(self, file_path: str | Path, check_links: bool = False) -> str:
        """Generate a user-friendly report for a DOCX manuscript."""

        extraction, issues = self.process_docx(file_path, check_links=check_links)
        return render_report(issues, extraction=extraction)

    def format_references(self, references: List[ReferenceEntry]) -> List[str]:
        return [self.formatter.format_apa(ref) for ref in references]

    def build_updated_docx(
        self, extraction: DocumentExtraction, issues: List[ValidationIssue]
    ) -> bytes:
        """Create a DOCX copy containing original text and a refreshed reference list."""

        paragraphs = [line for line in extraction.body_text.splitlines() if line]
        paragraphs.append("References")

        issues_by_ref = self._issues_by_reference(issues, extraction.references)

        for idx, ref in enumerate(extraction.references, start=1):
            formatted = self.formatter.format_apa(ref)
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
