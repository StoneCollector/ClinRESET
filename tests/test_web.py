"""
tests/test_web.py

Integration and end-to-end tests for the ClinRESET FastAPI web application.

Covers:
- GET /api/health endpoint
- POST /api/reports with non-PDF returns 400 with descriptive error
- POST /api/reports with real sample PDF returns 202 and job_id
- Polling GET /api/reports/{job_id} until status reaches 'done'
- Validating the 5 top-level keys of FinalReport.to_dict() in result
- Error handling for invalid/missing job IDs
- Serving of frontend index.html on root GET /
"""

from __future__ import annotations

import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from web.app import app

SAMPLE_PDF_PATH = Path("txt_extractor") / "sample_report.pdf"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_health_check(client: TestClient):
    """GET /api/health returns 200 and status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_non_pdf_returns_4xx(client: TestClient):
    """POST /api/reports with a non-PDF file must return 400 Bad Request with a clear message."""
    files = {
        "file": ("test_report.txt", b"This is not a PDF file", "text/plain")
    }
    response = client.post("/api/reports", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "pdf" in data["detail"].lower()


def test_get_nonexistent_job_id_returns_404(client: TestClient):
    """GET /api/reports/{job_id} with an unknown ID returns 404."""
    response = client.get("/api/reports/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()


def test_root_serves_html(client: TestClient):
    """GET / returns 200 and serves the frontend HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "ClinRESET" in response.text


def test_post_sample_pdf_and_poll_to_done(client: TestClient):
    """
    POST /api/reports with real sample PDF, verify 202 status and job_id,
    poll until done, and verify all 5 FinalReport keys.
    """
    assert SAMPLE_PDF_PATH.exists(), f"Sample PDF missing: {SAMPLE_PDF_PATH}"

    with open(SAMPLE_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    files = {
        "file": ("sample_report.pdf", pdf_bytes, "application/pdf")
    }

    # 1. Initiate upload
    response = client.post("/api/reports", files=files)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    job_id = data["job_id"]
    assert len(job_id) > 0

    # 2. Poll status until done or timeout (up to 60s)
    max_wait_seconds = 60
    start_time = time.time()
    final_data = None

    while time.time() - start_time < max_wait_seconds:
        poll_resp = client.get(f"/api/reports/{job_id}")
        assert poll_resp.status_code == 200
        poll_data = poll_resp.json()
        status = poll_data.get("status")

        if status == "done":
            final_data = poll_data
            break
        elif status == "failed":
            pytest.fail(f"Report job failed unexpectedly: {poll_data.get('error')}")

        time.sleep(1.0)

    assert final_data is not None, f"Report processing timed out after {max_wait_seconds}s"
    assert final_data["status"] == "done"
    assert "result" in final_data

    result = final_data["result"]

    # 3. Assert top-level keys match FinalReport.to_dict()
    expected_keys = {
        "report_summary",
        "key_findings",
        "measurements_of_interest",
        "context",
        "limitations",
    }
    assert set(result.keys()) == expected_keys, f"Expected keys {expected_keys}, got {set(result.keys())}"

    # 4. Check contents of each section
    summary = result["report_summary"]
    assert summary.get("report_type") == "echocardiography"
    assert summary.get("status") == "CONFIDENT"

    findings = result["key_findings"]
    assert len(findings) > 0
    # Every finding must have concept, assertion, explanation, alert_level, basis
    for f in findings:
        assert "concept" in f
        assert "assertion" in f
        assert "explanation" in f
        assert "alert_level" in f
        assert "basis" in f

    measurements = result["measurements_of_interest"]
    assert len(measurements) > 0
    # Every measurement must have concept, value, comparison, alert_level, basis
    for m in measurements:
        assert "concept" in m
        assert "value" in m
        assert "comparison" in m
        assert "alert_level" in m
        assert "basis" in m

    context = result["context"]
    assert len(context) > 0
    for c in context:
        assert "concepts" in c
        assert "relationship" in c
        assert "explanation" in c

    limitations = result["limitations"]
    assert len(limitations) > 0
    assert any("deterministic" in lim.lower() for lim in limitations)
