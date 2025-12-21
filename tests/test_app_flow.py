from reference_checker.app import ReferenceCheckerApp
from reference_checker.app import ReferenceCheckerApp
from reference_checker.metadata import StaticMetadataProvider
from reference_checker.models import ReferenceEntry


def test_process_text_detects_missing_reference_and_uncited():
    text = "Body cites [1] but not others.\nReferences\n[2] Roe, R. Missing citation. 2021."
    app = ReferenceCheckerApp()
    extraction, issues = app.process_text(text)
    codes = {issue.code for issue in issues}
    assert "missing-reference" in codes
    assert "uncited-reference" in codes
    assert extraction.metadata["matched"] == 0


def test_metadata_enrichment_applies_static_values():
    text = "Body cites [1].\nReferences\n[1] Doe, J. Article title."
    provider = StaticMetadataProvider({"1": {"year": "2022", "doi": "10.1000/xyz"}})
    app = ReferenceCheckerApp(metadata_provider=provider)
    extraction, issues = app.process_text(text)
    enriched = extraction.references[0]
    assert enriched.year == "2022"
    assert enriched.doi == "10.1000/xyz"
    assert all(issue.code != "missing-title" for issue in issues)


def test_formatting_produces_apa_like_output():
    entry = ReferenceEntry(
        raw_text="[1] Doe, J. Article title. Journal. 2020. 10(2):10-12. doi:10.1234/test",
        index_label="1",
        authors=["Doe, J."],
        title="Article title",
        journal="Journal",
        year="2020",
        volume="10",
        issue="2",
        pages="10-12",
        doi="10.1234/test",
    )
    app = ReferenceCheckerApp()
    formatted = app.format_references([entry])[0]
    assert "https://doi.org/10.1234/test" in formatted
    assert "(2020)" in formatted
