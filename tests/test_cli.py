from pathlib import Path

from reference_checker import cli


def test_cli_writes_outputs(tmp_path: Path):
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text(
        "Results cite [1].\nReferences\n1. Doe, J. Findings. 2020. https://example.org/article"
    )

    json_out = tmp_path / "results.json"
    docx_out = tmp_path / "updated.docx"
    bib_out = tmp_path / "refs.bib"

    exit_code = cli.main(
        [
            str(manuscript),
            "--json-output",
            str(json_out),
            "--updated-docx",
            str(docx_out),
            "--bibtex-output",
            str(bib_out),
        ]
    )

    assert exit_code == 0
    assert json_out.exists()
    assert docx_out.exists()
    assert bib_out.exists()


def test_cli_allows_stubbed_link_checks(monkeypatch, tmp_path: Path):
    calls = []

    class FakeVerifier:
        def __init__(self, *_, **__):
            pass

        def check(self, url: str):
            calls.append(url)
            from reference_checker.link_checker import LinkCheckResult

            return LinkCheckResult(url=url, reachable=False, status_code=500)

    monkeypatch.setattr(cli, "LinkVerifier", FakeVerifier)

    manuscript = tmp_path / "paper.txt"
    manuscript.write_text(
        "Results cite [1].\nReferences\n1. Doe, J. Findings. 2020. https://example.org/article"
    )

    cli.main([str(manuscript), "--check-links"])

    assert calls, "Fake verifier should have been invoked"
