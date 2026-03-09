import json

import pytest

from reference_checker.doaj import DoajClient, DoajJournalMatch


def test_doaj_client_returns_match_details():
    payload = json.dumps(
        {
            "total": 1,
            "results": [
                {
                    "id": "journal-123",
                    "bibjson": {
                        "title": "Journal of Testing",
                    },
                }
            ],
        }
    )
    client = DoajClient(fetcher=lambda _url, _timeout: payload)

    result = client.lookup_journal("Journal of Testing")

    assert result.found is True
    assert result.matched_title == "Journal of Testing"
    assert result.record_url == "https://doaj.org/api/v4/journals/journal-123"
    assert result.error == ""


def test_doaj_client_returns_not_found_for_empty_results():
    payload = json.dumps({"total": 0, "results": []})
    client = DoajClient(fetcher=lambda _url, _timeout: payload)

    result = client.lookup_journal("Missing Journal")

    assert result.found is False
    assert result.error == ""
    assert result.matched_title == ""


def test_build_rows_adds_doaj_fields_and_deduplicates_lookups():
    pytest.importorskip("pandas")
    import app as streamlit_app

    calls = []

    class FakePredatoryDb:
        def abbreviation_candidates(self, _journal, limit=20):
            return []

        def match_reference(self, *_args, **_kwargs):
            return []

    class FakeDoajClient:
        def lookup_journal(self, journal_title: str) -> DoajJournalMatch:
            calls.append(journal_title)
            return DoajJournalMatch(
                query=journal_title,
                found=True,
                matched_title="Journal of Testing",
                record_id="journal-123",
                record_url="https://doaj.org/api/v4/journals/journal-123",
            )

    reference_text = "\n".join(
        [
            "Doe, J. (2020). First article. Journal of Testing, 1, 1-10. https://doi.org/10.1000/one",
            "Roe, R. (2021). Second article. Journal of Testing, 2, 11-20. https://doi.org/10.1000/two",
            "Patel, P. (2019). Testing handbook. Testing Press.",
        ]
    )

    rows, pred_db_loaded = streamlit_app._build_rows(
        reference_text,
        fuzzy_threshold=0.88,
        max_fuzzy_matches=3,
        pred_db=FakePredatoryDb(),
        check_doaj=True,
        doaj_client=FakeDoajClient(),
    )

    assert pred_db_loaded is True
    assert len(rows) == 3
    assert calls.count("Journal of Testing") == 1
    assert rows[0]["DOAJ status"] == "Registered"
    assert rows[0]["DOAJ matched title"] == "Journal of Testing"
    assert rows[0]["DOAJ link"] == "https://doaj.org/api/v4/journals/journal-123"
    assert rows[1]["DOAJ status"] == "Registered"
    assert rows[2]["DOAJ status"] == "Registered"
