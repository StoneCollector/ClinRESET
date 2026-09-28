"""
Report processing API routes for ClinRESET Web API.
Handles document upload, sample selection, and complete pipeline execution.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.web.pipeline import process_clinical_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["Reports"])

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data",
)


class SampleReportRequest(BaseModel):
    sample_path: str


@router.get("/samples")
def list_sample_reports() -> Dict[str, Any]:
    """Returns categorized list of available clinical sample PDFs in data/."""
    modalities = ["echo", "ct scans", "mri", "ultrasound", "xray", "general"]
    samples_by_modality: Dict[str, List[Dict[str, str]]] = {}

    for mod in modalities:
        mod_dir = os.path.join(DATA_DIR, mod)
        samples_by_modality[mod] = []
        if os.path.exists(mod_dir):
            for fname in sorted(os.listdir(mod_dir)):
                if fname.lower().endswith(".pdf"):
                    rel_path = os.path.join(mod, fname)
                    samples_by_modality[mod].append({
                        "filename": fname,
                        "relative_path": rel_path,
                        "modality": mod,
                    })

    return {"samples": samples_by_modality}


@router.post("/upload")
async def upload_and_process_report(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Uploads a PDF report and runs the complete simplification pipeline."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        result = process_clinical_pdf(
            pdf_bytes=content,
            filename=file.filename,
        )
        return result
    except Exception as e:
        logger.exception("Error processing uploaded PDF")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF report: {str(e)}")


@router.post("/sample")
def process_sample_report(req: SampleReportRequest) -> Dict[str, Any]:
    """Processes a pre-existing sample PDF report from the data directory."""
    full_path = os.path.join(DATA_DIR, req.sample_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail=f"Sample report not found: {req.sample_path}")

    filename = os.path.basename(full_path)
    try:
        result = process_clinical_pdf(
            pdf_path=full_path,
            filename=filename,
        )
        return result
    except Exception as e:
        logger.exception("Error processing sample PDF")
        raise HTTPException(status_code=500, detail=f"Failed to process sample report: {str(e)}")
