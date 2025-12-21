import json

from reference_checker.app import ReferenceCheckerApp
from reference_checker.crossref import (
    CrossrefClient,
    CrossrefMetadataProvider,
    OnlineReferenceVerifier,
)
from reference_checker.models import ReferenceEntry, ValidationIssue


def _fake_crossref_response() -> str:
    return json.dumps(
        {
            "message": {
                "title": ["Trusted Article Title"],
                "author": [{"family": "Doe", "given": "Jane"}],
                "container-title": ["Journal of Trust"],
                "issued": {"date-parts": [[2022]]},
                "volume": "4",
                "issue": "2",
                "page": "101-110",
                "DOI": "10.5555/example",
                "type": "journal-article",
            }
        }
    )


def test_crossref_provider_completes_missing_metadata():
    client = CrossrefClient(fetcher=lambda _url, _timeout: _fake_crossref_response())
    provider = CrossrefMetadataProvider(client=client)

    entry = ReferenceEntry(raw_text="Example", doi="10.5555/example")
    enriched = provider.enrich(entry)

    assert enriched.title == "Trusted Article Title"
    assert enriched.authors == ["Doe, Jane"]
    assert enriched.journal == "Journal of Trust"
    assert enriched.year == "2022"
    assert enriched.volume == "4"
    assert enriched.issue == "2"
    assert enriched.pages == "101-110"
    assert enriched.doi == "10.5555/example"
    assert enriched.entry_type == "journal-article"


def test_online_verifier_flags_mismatches():
    client = CrossrefClient(fetcher=lambda _url, _timeout: _fake_crossref_response())
    verifier = OnlineReferenceVerifier(client=client)

    entry = ReferenceEntry(
        raw_text="Example",
        doi="10.5555/example",
        title="Wrong Title",
        authors=["Smith, Alex"],
        journal="Other Journal",
        year="1999",
    )

    issues = verifier.verify(entry)
    codes = {issue.code for issue in issues}

    assert {"title-mismatch", "author-mismatch", "journal-mismatch", "year-mismatch"}.issubset(
        codes
    )


def test_app_process_text_invokes_online_verifier(monkeypatch):
    checks = []

    class FakeVerifier:
        def __init__(self, *_, **__):
            pass

        def verify(self, ref: ReferenceEntry):
            checks.append(ref.raw_text)
            return [ValidationIssue(code="online-check", message="checked", context=ref.raw_text)]

    app = ReferenceCheckerApp(online_verifier=FakeVerifier())

    text = "Body cites [1].\nReferences\n[1] Example ref."
    _, issues = app.process_text(text, verify_online=True)

    assert checks == ["[1] Example ref."]
    assert any(issue.code == "online-check" for issue in issues)
