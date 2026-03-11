from reference_checker.citation_extractor import CitationExtractor
from reference_checker.parsers import DocumentParser
from reference_checker.reference_parser import ReferenceListParser
from reference_checker.validation import validate_reference_completeness
from reference_checker.models import ReferenceEntry


def test_document_parser_splits_references():
    text = "Introduction text.\nReferences\n[1] Doe, J. Study. 2020."
    parser = DocumentParser()
    body, refs = parser.split_sections(text)
    assert "Introduction" in body
    assert "References" not in body
    assert "Doe" in refs


def test_document_parser_accepts_reference_list_heading():
    text = "Introduction text.\nReference List\n[1] Doe, J. Study. 2020."
    parser = DocumentParser()
    body, refs = parser.split_sections(text)

    assert "Introduction" in body
    assert "Reference List" not in body
    assert "Doe" in refs


def test_citation_extractor_detects_numeric_and_author_year():
    text = "As shown in [1, 2-3] and (Smith 2020), references matter."
    extractor = CitationExtractor()
    citations = extractor.extract(text)
    keys = extractor.extract_keys(citations)
    assert "1" in keys
    assert "2" in keys
    assert "3" in keys
    assert "smith2020" in keys


def test_reference_parser_extracts_fields():
    refs_text = "[1] Doe, J.; Roe, R. Article title. Journal Name. 2020; 10(2):10-12. https://doi.org/10.1234/example"
    parser = ReferenceListParser()
    entries = parser.parse(refs_text)
    assert entries[0].index_label == "1"
    assert "Doe" in entries[0].authors[0]
    assert entries[0].year == "2020"
    assert entries[0].doi == "10.1234/example"


def test_reference_parser_handles_author_initials_without_field_shift():
    refs_text = "[1] Doe, J.; Roe, R. Article title. Journal Name. 2020;10(2):10-12."
    parser = ReferenceListParser()
    entry = parser.parse(refs_text)[0]

    assert entry.authors[:2] == ["Doe, J.", "Roe, R"]
    assert entry.title == "Article title"
    assert entry.journal == "Journal Name"


def test_reference_parser_handles_mdpi_style_abbreviated_journal_with_tags():
    refs_text = (
        "Beck, A.T.; Epstein, N.; Brown, G.; Steer, R.A. "
        "An inventory for measuring clinical anxiety: Psychometric properties. "
        "J. Consult Clin. Psychol. 1988, 56, 893–897. [Google Scholar] [CrossRef]"
    )
    parser = ReferenceListParser()
    entry = parser.parse(refs_text)[0]

    assert entry.year == "1988"
    assert entry.title == "An inventory for measuring clinical anxiety: Psychometric properties"
    assert entry.journal == "J. Consult Clin. Psychol"


def test_reference_parser_handles_int_j_cardiol_style_with_resource_tags():
    refs_text = (
        "Li, S.; Zhou, X.; Yu, L.; Jiang, H. "
        "Low level non-invasive vagus nerve stimulation: A novel feasible therapeutic approach for atrial fibrillation. "
        "Int. J. Cardiol. 2015, 182, 189–190. [Google Scholar] [CrossRef] [PubMed]"
    )
    parser = ReferenceListParser()
    entry = parser.parse(refs_text)[0]

    assert entry.year == "2015"
    assert entry.journal == "Int. J. Cardiol"


def test_book_reference_does_not_require_locator():
    entry = ReferenceEntry(
        raw_text="Doe, J. Testing handbook. Testing Press. 2019.",
        authors=["Doe, J."],
        title="Testing handbook",
        publisher="Testing Press",
        year="2019",
        entry_type="book",
    )

    issues = validate_reference_completeness(entry)
    codes = {issue.code for issue in issues}

    assert "missing-locator" not in codes
