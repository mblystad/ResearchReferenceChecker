from reference_checker.app import ReferenceCheckerApp
from reference_checker.parsers import DocumentParser


def test_docx_text_loading(sample_docx_path):
    parser = DocumentParser()
    text = parser.load_docx_text(sample_docx_path)

    assert "Dummy Manuscript for Reference Checker" in text
    assert "References" in text


def test_user_report_for_docx_includes_counts_and_issues(sample_docx_path):
    app = ReferenceCheckerApp()

    report = app.user_report_for_docx(sample_docx_path)

    assert "Reference Validation Report" in report
    assert "Citations detected: 4" in report
    assert "Reference entries: 4" in report
    assert "Matched pairs: 3" in report
    assert "uncited-reference" in report
    assert "missing-locator" in report
