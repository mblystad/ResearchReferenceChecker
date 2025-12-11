import re

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from reference_checker.web import app


client = TestClient(app)


def test_homepage_renders_forms():
    response = client.get("/")

    assert response.status_code == 200
    assert "Reference Checker" in response.text
    assert "tailwind" in response.text.lower()
    assert "name=\"file\"" in response.text
    assert "name=\"text\"" in response.text


def test_analyze_text_returns_report():
    response = client.post(
        "/analyze-text",
        data={
            "text": "Introduction with citation [1]\n\nReferences\n[1] Smith, J. Article title. Journal. 2020."
        },
    )

    assert response.status_code == 200
    assert "Reference Validation Report" in response.text
    assert "Citations detected" in response.text


def test_analyze_docx_upload(sample_docx_path):
    with sample_docx_path.open("rb") as handle:
        response = client.post(
            "/analyze-docx",
            files={
                "file": (
                    sample_docx_path.name,
                    handle,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 200
    assert "Reference Validation Report" in response.text
    assert "Matched pairs" in response.text
    assert "Download updated DOCX" in response.text

    match = re.search(r"/download/([a-f0-9]+)", response.text)
    assert match is not None

    download = client.get(f"/download/{match.group(1)}")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
