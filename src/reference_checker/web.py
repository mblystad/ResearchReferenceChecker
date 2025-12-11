"""FastAPI + Tailwind interface for the reference checker app.

Run with:
    uvicorn reference_checker.web:app --reload
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from secrets import token_hex
from typing import Dict

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from .app import ReferenceCheckerApp
from .report import render_report

app = FastAPI(title="Reference Checker", description="Validate references from the browser")

checker = ReferenceCheckerApp()
generated_exports: Dict[str, Path] = {}


def _layout(content: str) -> str:
    """Wrap provided content in a Tailwind-powered HTML page."""

    return f"""
    <!doctype html>
    <html lang=\"en\" class=\"h-full bg-gray-50\">
    <head>
        <meta charset=\"utf-8\" />
        <title>Reference Checker</title>
        <link href=\"https://cdn.jsdelivr.net/npm/tailwindcss@3.4.4/dist/tailwind.min.css\" rel=\"stylesheet\" />
    </head>
    <body class=\"min-h-full py-10\">
        <div class=\"max-w-5xl mx-auto px-4\">
            <div class=\"bg-white shadow rounded-lg p-6\">
                <h1 class=\"text-3xl font-semibold text-gray-900\">Reference Checker</h1>
                <p class=\"text-gray-600 mt-2\">Upload a DOCX manuscript or paste text to see the validation report and download an updated reference list copy.</p>
                {content}
            </div>
        </div>
    </body>
    </html>
    """


def _form_page(report: str | None = None, download_token: str | None = None) -> str:
    """Render the landing page with optional report output and download link."""

    docx_form = """
    <form action=\"/analyze-docx\" method=\"post\" enctype=\"multipart/form-data\" class=\"bg-gray-50 border border-gray-200 rounded-lg p-4 mt-6\">
        <h2 class=\"text-xl font-semibold text-gray-800\">Upload DOCX</h2>
        <p class=\"text-gray-600 text-sm mb-3\">We will validate references and produce a downloadable copy with flagged missing details.</p>
        <label class=\"block text-sm font-medium text-gray-700 mb-2\" for=\"file\">DOCX manuscript</label>
        <input type=\"file\" name=\"file\" accept=\".docx\" required class=\"block w-full text-sm text-gray-800\" />
        <button type=\"submit\" class=\"mt-4 inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-md shadow hover:bg-indigo-700\">Validate DOCX</button>
    </form>
    """

    text_form = """
    <form action=\"/analyze-text\" method=\"post\" class=\"bg-gray-50 border border-gray-200 rounded-lg p-4 mt-6\">
        <h2 class=\"text-xl font-semibold text-gray-800\">Paste Manuscript Text</h2>
        <p class=\"text-gray-600 text-sm mb-3\">Include the References section to see citation matching results.</p>
        <label class=\"block text-sm font-medium text-gray-700 mb-2\" for=\"text\">Manuscript text</label>
        <textarea name=\"text\" required placeholder=\"Paste manuscript text including References section...\" class=\"w-full h-44 border border-gray-300 rounded-md p-3 text-sm\"></textarea>
        <button type=\"submit\" class=\"mt-4 inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-md shadow hover:bg-indigo-700\">Validate Text</button>
    </form>
    """

    report_block = ""
    if report:
        report_block = f"""
        <div class=\"mt-8\">
            <h2 class=\"text-xl font-semibold text-gray-800\">Validation Report</h2>
            <pre class=\"mt-3 bg-gray-900 text-green-100 p-4 rounded-lg whitespace-pre-wrap text-sm\">{report}</pre>
        </div>
        """

    download_block = ""
    if download_token:
        download_block = f"""
        <div class=\"mt-4\">
            <a class=\"inline-flex items-center px-4 py-2 bg-emerald-600 text-white rounded-md shadow hover:bg-emerald-700\" href=\"/download/{download_token}\">Download updated DOCX</a>
            <p class=\"text-sm text-gray-600 mt-2\">Includes the original text plus a refreshed reference list with missing details highlighted.</p>
        </div>
        """

    return _layout(docx_form + text_form + report_block + download_block)


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    """Serve the upload/text submission form."""

    return HTMLResponse(_form_page())


@app.post("/analyze-text", response_class=HTMLResponse)
async def analyze_text(text: str = Form(...)) -> HTMLResponse:
    """Process pasted manuscript text and return a formatted report."""

    extraction, issues = checker.process_text(text)
    report = render_report(issues, extraction=extraction)
    return HTMLResponse(_form_page(report))


@app.post("/analyze-docx", response_class=HTMLResponse)
async def analyze_docx(file: UploadFile = File(...)) -> HTMLResponse:
    """Process an uploaded DOCX file and return a formatted report."""

    if file.content_type not in {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only DOCX files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "").suffix or ".docx") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        extraction, issues = checker.process_docx(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    updated_bytes = checker.build_updated_docx(extraction, issues)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as export_tmp:
        export_tmp.write(updated_bytes)
        token = token_hex(8)
        generated_exports[token] = Path(export_tmp.name)

    report = render_report(issues, extraction=extraction)
    return HTMLResponse(_form_page(report, download_token=token))


@app.get("/download/{token}")
async def download_updated(token: str, tasks: BackgroundTasks) -> FileResponse:
    """Serve a generated DOCX with updated reference list annotations."""

    path = generated_exports.pop(token, None)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Export not found or expired")

    tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="reference-checker-updated.docx",
    )


def main() -> None:
    """Run the FastAPI app using uvicorn."""

    import uvicorn

    uvicorn.run("reference_checker.web:app", host="0.0.0.0", port=8000, reload=False)


__all__ = ["app", "main"]
