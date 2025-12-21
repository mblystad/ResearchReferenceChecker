from reference_checker.app import ReferenceCheckerApp
from reference_checker.link_checker import LinkVerifier
from reference_checker.validation import validate_reference_links
from reference_checker.models import ReferenceEntry


def test_validate_reference_links_reports_unreachable():
    verifier = LinkVerifier(requester=lambda url: 404)
    ref = ReferenceEntry(raw_text="Ref A", doi="10.1234/example")

    issues = validate_reference_links(ref, verifier)

    assert any(issue.code == "doi-unreachable" for issue in issues)


def test_process_text_can_check_links():
    calls = []

    def requester(url: str) -> int:
        calls.append(url)
        return 503

    verifier = LinkVerifier(requester=requester)
    app = ReferenceCheckerApp(link_verifier=verifier)
    text = "Intro cites [1].\nReferences\n1. Doe, J. Example title. 2020. 10.1000/example"

    _, issues = app.process_text(text, check_links=True)

    assert calls, "link verifier should be used when check_links=True"
    assert any(issue.code == "doi-unreachable" for issue in issues)
