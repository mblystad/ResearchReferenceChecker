from reference_checker.models import ReferenceEntry
from reference_checker.web_metadata import WebPageMetadataProvider
from reference_checker.models import ReferenceEntry


HTML_FIXTURE = """
<html>
<head>
<title>Fallback Title</title>
<meta name="citation_title" content="Scraped Article" />
<meta name="citation_author" content="Doe, Jane" />
<meta name="citation_author" content="Smith, John" />
<meta name="citation_journal_title" content="Journal of Scraping" />
<meta name="citation_year" content="2024" />
<meta name="citation_volume" content="12" />
<meta name="citation_issue" content="3" />
<meta name="citation_firstpage" content="101" />
<meta name="citation_lastpage" content="110" />
<meta name="citation_doi" content="10.1234/example" />
</head>
<body></body>
</html>
"""


def test_web_metadata_provider_fills_missing_fields():
    calls: list[str] = []

    def fake_fetch(url: str, _timeout: float) -> str:
        calls.append(url)
        return HTML_FIXTURE

    provider = WebPageMetadataProvider(fetcher=fake_fetch)

    entry = ReferenceEntry(raw_text="Example", url="https://example.org/article")

    enriched = provider.enrich(entry)

    assert enriched.title == "Scraped Article"
    assert enriched.authors == ["Doe, Jane", "Smith, John"]
    assert enriched.journal == "Journal of Scraping"
    assert enriched.year == "2024"
    assert enriched.volume == "12"
    assert enriched.issue == "3"
    assert enriched.pages == "101-110"
    assert enriched.doi == "10.1234/example"
    assert calls == ["https://example.org/article"]


def test_web_metadata_provider_uses_doi_when_url_missing():
    calls: list[str] = []

    def fake_fetch(url: str, _timeout: float) -> str:
        calls.append(url)
        return "<html><head><meta name='citation_title' content='Title from DOI' /></head></html>"

    provider = WebPageMetadataProvider(fetcher=fake_fetch)

    entry = ReferenceEntry(raw_text="Example", doi="10.5555/example")
    enriched = provider.enrich(entry)

    assert enriched.title == "Title from DOI"
    assert calls == ["https://doi.org/10.5555/example"]
