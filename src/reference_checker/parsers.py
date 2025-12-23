"""Parsers for extracting structured content from manuscripts."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Tuple

from xml.etree import ElementTree


class DocumentParser:
    """Splits manuscript text into body and reference sections."""

    REFERENCE_HEADINGS = re.compile(r"^(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE)

    def split_sections(self, text: str) -> Tuple[str, str]:
        """Return (body_text, references_text) based on heading detection."""
        match = self.REFERENCE_HEADINGS.search(text)
        if not match:
            return text, ""
        start = match.end()
        return text[: start].strip(), text[start:].strip()

    def load_docx_text(self, file_path: str | Path) -> str:
        """Read a DOCX file and return its text content with paragraph spacing."""

        doc_path = Path(file_path)
        with zipfile.ZipFile(doc_path) as archive:
            xml = archive.read("word/document.xml")
        tree = ElementTree.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for para in tree.findall(".//w:p", namespace):
            texts = [node.text for node in para.findall(".//w:t", namespace) if node.text]
            paragraphs.append("".join(texts))
        return "\n".join(paragraphs)

    def load_pdf_text(self, file_path: str | Path) -> str:
        """Read a PDF file and return its extracted text."""
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency error path
            raise RuntimeError(
                "PDF support requires the 'pypdf' package. Install it to process PDFs."
            ) from exc

        pdf_path = Path(file_path)
        reader = PdfReader(str(pdf_path))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text:
                pages.append(text)
        return "\n".join(pages)

    def load_text(self, file_path: str | Path) -> str:
        """Load text from supported manuscript formats."""
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".docx":
            return self.load_docx_text(path)
        if suffix == ".pdf":
            return self.load_pdf_text(path)
        return path.read_text()
