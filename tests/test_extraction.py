from reference_checker.citation_extractor import CitationExtractor
from reference_checker.parsers import DocumentParser
from reference_checker.reference_parser import ReferenceListParser


def test_document_parser_splits_references():
    text = "Introduction text.\nReferences\n[1] Doe, J. Study. 2020."
    parser = DocumentParser()
    body, refs = parser.split_sections(text)
    assert "Introduction" in body
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
