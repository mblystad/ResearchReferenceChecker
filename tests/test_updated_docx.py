import tempfile
from pathlib import Path

from reference_checker.app import ReferenceCheckerApp


def test_build_updated_docx_highlights_missing_metadata():
    app = ReferenceCheckerApp()
    text = "Intro cites [1]\n\nReferences\n[1] Smith, J."

    extraction, issues = app.process_text(text)
    doc_bytes = app.build_updated_docx(extraction, issues)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(doc_bytes)
        temp_path = tmp.name

    try:
        parsed_text = app.parser.load_docx_text(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    paragraph_texts = parsed_text.splitlines()

    assert any("Intro cites" in p for p in paragraph_texts)
    assert any("Missing details" in p for p in paragraph_texts)
    assert any("Smith" in p for p in paragraph_texts)
