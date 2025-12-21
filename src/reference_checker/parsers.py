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
