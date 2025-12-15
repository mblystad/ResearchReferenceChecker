import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import pytest

from reference_checker.app import ReferenceCheckerApp


@pytest.fixture()
def sample_docx_path(tmp_path: Path) -> Path:
    """Create a temporary DOCX file mirroring the original sample content."""

    paragraphs = [
        "Dummy Manuscript for Reference Checker",
        (
            "This short document includes dummy text with in-text citations [1] and [2] "
            "to support testing of the reference checker workflow. It also mentions an "
            "author-based citation (Doe, 2021) and highlights the importance of consistent "
            "metadata [3]. Additional filler sentences ensure the content spans roughly one "
            "page when rendered in a standard word processor."
        ),
        (
            "Methodologically, the sample text outlines a hypothetical pipeline with "
            "preprocessing, citation detection, reference parsing, metadata enrichment, "
            "and validation reporting [1,3]. The details are intentionally lightweight so "
            "that automated tools can focus on references without modifying the "
            "surrounding narrative."
        ),
        (
            "Another paragraph adds variety by discussing limitations, potential error "
            "cases, and logging needs [2]. It hints at uncited references and dangling "
            "citations to see how the checker flags missing links."
        ),
        "References",
        "[1] Doe J. Sample article title. Journal of Testing. 2021;10(2):123-130. doi:10.1234/jt.2021.456.",
        "[2] Smith A, Lee B. Another study on testing. Proceedings of the Reference Checking Conference; 2020. Available from: https://example.com/testing.",
        "[3] Patel R. Data validation handbook. Testing Press; 2019.",
        "[4] Adams K. Preprint example on reference integrity. bioRxiv; 2023. doi:10.1101/2023.12345.",
    ]

    data = ReferenceCheckerApp._build_minimal_docx(paragraphs)  # type: ignore[attr-defined]
    docx_path = tmp_path / "sample_manuscript.docx"
    docx_path.write_bytes(data)
    return docx_path
