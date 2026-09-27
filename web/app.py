"""
web/app.py

FastAPI backend application for ClinRESET web report processing.

Endpoints:
- POST /api/reports: Accept multipart PDF upload, start async threadpool processing, return 202 with job_id.
- GET /api/reports/{job_id}: Return current status ('processing' | 'failed' | 'done') and results.
- GET /api/health: Service health check.
- GET /: Serve the single-page application frontend.
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import threading
from typing import Any
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("web.app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="ClinRESET Web API",
    description="Medical Report Simplification and Deterministic Clinical Explanation Engine",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for asynchronous processing jobs
JOBS: dict[str, dict[str, Any]] = {}

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
UPLOAD_DIR = BASE_DIR / "output" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _process_report_job(job_id: str, pdf_path: Path) -> None:
    """
    Background worker function that executes document extraction and report assembly.
    """
    try:
        from extraction.pipeline import extract_document
        from reporting.builder import build_final_report

        output_root = BASE_DIR / "output"
        result = extract_document(pdf_path, output_root=output_root, save_output=True)

        # Check validation status
        if result.validation and result.validation.status == "FAILED":
            warn_msg = "; ".join(result.validation.warnings) if result.validation.warnings else "Document quality check failed"
            JOBS[job_id] = {
                "status": "failed",
                "error": f"Extraction failed: validation status FAILED ({warn_msg})",
            }
            return

        # Check classification status
        if (
            result.classification is None
            or result.classification.status in ("UNKNOWN", "AMBIGUOUS")
            or result.classification.report_type == "unknown"
        ):
            rep_type = getattr(result.classification, "report_type", "unknown")
            rep_stat = getattr(result.classification, "status", "UNKNOWN")
            JOBS[job_id] = {
                "status": "failed",
                "error": f"Report classification failed: unsupported or ambiguous report type '{rep_type}' (status: {rep_stat})",
            }
            return

        # Build final report
        report_dict = result.to_dict()
        final_report = build_final_report(report_dict)
        JOBS[job_id] = {
            "status": "done",
            "result": final_report.to_dict(),
        }
    except Exception as exc:
        logger.exception("Error processing report job %s: %s", job_id, exc)
        JOBS[job_id] = {
            "status": "failed",
            "error": f"Processing error: {str(exc)}",
        }


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok"}


@app.post("/api/reports", status_code=202)
async def upload_report(file: UploadFile = File(...)):
    """
    Accept PDF file upload and launch asynchronous extraction and reporting job.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a PDF.")

    job_id = str(uuid.uuid4())
    temp_pdf_path = UPLOAD_DIR / f"{job_id}.pdf"

    try:
        with open(temp_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store uploaded PDF: {exc}")
    finally:
        file.file.close()

    # Initialize job state
    JOBS[job_id] = {"status": "processing"}

    # Start background execution in a dedicated daemon thread to avoid blocking the event loop
    worker_thread = threading.Thread(
        target=_process_report_job,
        args=(job_id, temp_pdf_path),
        daemon=True,
    )
    worker_thread.start()

    return {"job_id": job_id}


@app.get("/api/reports/{job_id}")
async def get_report_status(job_id: str):
    """
    Retrieve current processing status or completed report result.
    """
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Report job not found.")
    return JOBS[job_id]


# Serve frontend static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the single-page application frontend."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "ClinRESET Web API"}
