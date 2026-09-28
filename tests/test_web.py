"""
Tests for ClinRESET Web API, Methodology Studio, and End-to-End Pipeline.
Validates FastAPI routes, configuration updates, live extraction testing,
sample processing, and static frontend delivery.
"""

import io
import os
import pytest
from fastapi.testclient import TestClient

from src.web.app import app
from src.web.state import CONFIG_STATE


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "ClinRESET"
    assert data["version"] == "2.0.0"


def test_serve_static_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ClinRESET" in response.text
    assert "Methodology Studio" in response.text
    assert "Report Simplifier" in response.text


def test_serve_static_assets(client):
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    assert "ClinRESET" in css_res.text

    js_res = client.get("/static/js/app.js")
    assert js_res.status_code == 200
    assert "ClinRESET" in js_res.text


def test_get_methodologies(client):
    response = client.get("/api/methodologies")
    assert response.status_code == 200
    data = response.json()
    assert "active_backend" in data
    assert "availability" in data
    assert "heuristic" in data["availability"]
    assert data["availability"]["heuristic"] is True
    assert "backend_descriptions" in data
    assert "config" in data


def test_configure_methodology(client):
    # Test valid configure
    payload = {
        "active_backend": "heuristic",
        "ollama_url": "http://localhost:11434",
        "ollama_model": "qwen2.5:1.5b",
    }
    response = client.post("/api/methodologies/configure", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["current_config"]["active_backend"] == "heuristic"
    assert data["current_config"]["ollama_url"] == "http://localhost:11434"

    # Test invalid configure
    invalid_payload = {"active_backend": "magic_ai_9000"}
    bad_res = client.post("/api/methodologies/configure", json=invalid_payload)
    assert bad_res.status_code == 400


def test_test_extraction_sandbox(client):
    sentence = "Liver is enlarged in size (~15.8cm), normal in outline; no focal lesion seen."
    payload = {
        "sentence": sentence,
        "backend": "heuristic",
    }
    response = client.post("/api/methodologies/test", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["backend_used"] == "heuristic"
    assert data["sentence"] == sentence
    assert "elapsed_ms" in data
    assert data["count"] > 0
    concepts = [c["concept"] for c in data["concepts_extracted"]]
    assert any("liver" in c.lower() or "lesion" in c.lower() for c in concepts)
    # Grounding check
    assert all(c["is_grounded"] for c in data["concepts_extracted"])


def test_list_sample_reports(client):
    response = client.get("/api/reports/samples")
    assert response.status_code == 200
    data = response.json()
    assert "samples" in data
    # At least some modality directories exist
    samples = data["samples"]
    assert isinstance(samples, dict)


def test_process_sample_report(client):
    # Fetch available sample reports
    samples_res = client.get("/api/reports/samples")
    samples_data = samples_res.json()["samples"]

    # Prefer a concise sample report (e.g. xray or ultrasound) for fast test execution
    sample_path = None
    for preferred in ["xray", "ultrasound", "general", "mri", "echo", "ct scans"]:
        if preferred in samples_data and samples_data[preferred]:
            sample_path = samples_data[preferred][0]["relative_path"]
            break

    if not sample_path:
        pytest.skip("No sample reports found in data directory")

    response = client.post("/api/reports/sample", json={"sample_path": sample_path})
    assert response.status_code == 200
    data = response.json()
    assert "filename" in data
    assert "report_type" in data
    assert "patient_explanation" in data
    assert (
        "patient_summary" in data["patient_explanation"]
        or "summary" in data["patient_explanation"]
    )
    assert "findings" in data
    assert "interpretation" in data
    assert "triage_summary" in data["interpretation"]


def test_upload_non_pdf_fails(client):
    txt_file = io.BytesIO(b"This is not a PDF file.")
    response = client.post(
        "/api/reports/upload",
        files={"file": ("report.txt", txt_file, "text/plain")},
    )
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]
