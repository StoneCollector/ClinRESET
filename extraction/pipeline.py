"""
Production extraction pipeline.

This module implements extract_document(pdf_path) — the single public
entry point for the entire extraction layer.

Production extraction order (FIXED — do not modify):

    STEP 1:  Inspect PDF
    STEP 2:  Determine digital vs scanned
    STEP 3:  digital PDF  → PyMuPDF4LLM
    STEP 4:  Validate PyMuPDF4LLM result
    STEP 5:  GOOD         → use it
    STEP 6:  DEGRADED/FAILED → coordinate extractor
    STEP 7:  Validate coordinate result
    STEP 8:  scanned PDF  → OCR interface
    STEP 9:  Normalise selected result
    STEP 10: Run final validation (already done per-extractor)
    STEP 11: Save raw output and normalised JSON
    STEP 12: Return ExtractionResult

Libraries that are NOT part of the production pipeline:
    pdfplumber, pypdfium2, pypdf, textract, unstructured, marker-pdf

No medical interpretation is performed here.
"""

from __future__ import annotations

import json
import logging
import traceback
from pathlib import Path
from typing import Any, Optional

from extraction.inspector import PDFInspector, InspectionResult
from extraction.extractors.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
from extraction.extractors.coordinate_extractor import CoordinateExtractor
from extraction.ocr.interface import OCRExtractor
from extraction.validator import validate_extraction
from extraction.normaliser import normalise
from extraction.models import ExtractionResult, DocumentMeta, RawOutput, ValidationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 2 classification (optional, non-breaking)
# ---------------------------------------------------------------------------

def _classify_result(result: ExtractionResult) -> None:
    """
    Run the Phase 2 classifier and attach the result to *result*.

    This function is deliberately defensive: any exception from the
    classification layer is caught and logged so that Phase 1 output
    is never affected by a Phase 2 failure.
    """
    try:
        from classification.classifier import classify
        classification = classify(result)
        result.classification = classification
        logger.info(
            "Classification: type=%s status=%s confidence=%.3f",
            classification.report_type,
            classification.status,
            classification.confidence,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Classification step failed (non-fatal): %s", exc)
        result.classification = None


def _extract_clinical_info(result: ExtractionResult) -> None:
    """
    Run the Phase 3 clinical extraction layer on an ExtractionResult in-place.

    This function is deliberately defensive: any exception from the
    clinical extraction layer is caught and logged so that Phase 1 and 2
    outputs are never affected by a Phase 3 failure.
    """
    try:
        from clinical_extraction import extract_clinical_info

        clinical_info = extract_clinical_info(result)
        result.clinical_information = clinical_info
        logger.info(
            "Clinical extraction: entities=%d, measurements=%d, findings=%d, anatomy=%d, relationships=%d",
            len(clinical_info.entities),
            len(clinical_info.measurements),
            len(clinical_info.findings),
            len(clinical_info.anatomy),
            len(clinical_info.relationships),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Clinical extraction step failed (non-fatal): %s", exc)
        result.clinical_information = None


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------


def _make_output_dirs(pdf_path: Path, output_root: Path) -> dict[str, Path]:
    """Create and return the per-document output directories."""
    doc_dir = output_root / pdf_path.stem
    dirs = {
        "root": doc_dir,
        "raw": doc_dir / "raw",
        "normalized": doc_dir / "normalized",
        "validation": doc_dir / "validation",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def _save_outputs(
    result: ExtractionResult,
    dirs: dict[str, Path],
) -> None:
    """Persist raw Markdown, normalised JSON, and validation JSON."""

    # Raw Markdown / text.
    raw_md_path = dirs["raw"] / "extraction.md"
    raw_md_path.write_text(
        result.raw.markdown or result.raw.text,
        encoding="utf-8",
    )

    # Normalised JSON.
    normalised_path = dirs["normalized"] / "report.json"
    normalised_path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Validation JSON (separate file for quick inspection).
    validation_path = dirs["validation"] / "validation.json"
    validation_path.write_text(
        json.dumps(
            {
                "status": result.validation.status,
                "warnings": result.validation.warnings,
                "scores": result.validation.scores,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info("Output saved to: %s", dirs["root"])


# ---------------------------------------------------------------------------
# Structured failure helper
# ---------------------------------------------------------------------------


def _make_failure_result(
    pdf_path: Path,
    inspection: Optional[InspectionResult],
    extractor_name: str,
    errors: list[str],
) -> ExtractionResult:
    """
    Build an ExtractionResult that signals a complete extraction failure.
    """
    page_count = inspection.page_count if inspection else 0
    source_type = inspection.source_type if inspection else "unknown"

    return ExtractionResult(
        document=DocumentMeta(
            file_name=pdf_path.name,
            page_count=page_count,
            source_type=source_type,
            extractor=extractor_name,
        ),
        raw=RawOutput(),
        validation=ValidationResult(
            status="FAILED",
            warnings=errors,
        ),
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def extract_document(
    pdf_path: str | Path,
    output_root: str | Path = "output",
    save_output: bool = True,
) -> ExtractionResult:
    """
    Production extraction pipeline entry point.

    Parameters
    ----------
    pdf_path:
        Path to the medical PDF.
    output_root:
        Directory under which per-document output directories are created.
    save_output:
        When True (default), write raw/normalised/validation files to disk.

    Returns
    -------
    ExtractionResult
        The normalised intermediate representation.  The caller should
        check result.validation.status to determine quality.
    """

    pdf_path = Path(pdf_path).resolve()
    output_root = Path(output_root)

    logger.info("=" * 60)
    logger.info("extract_document: %s", pdf_path)

    # ------------------------------------------------------------------
    # STEP 1 & 2: Inspect PDF / determine route
    # ------------------------------------------------------------------

    inspection: Optional[InspectionResult] = None

    try:
        inspector = PDFInspector(pdf_path)
        inspection = inspector.inspect()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("PDF inspection failed: %s", exc)
        return _make_failure_result(
            pdf_path, None, "none", [str(exc)]
        )
    except Exception as exc:
        logger.error("Unexpected inspection error: %s", exc)
        logger.debug(traceback.format_exc())
        return _make_failure_result(
            pdf_path, None, "none", [f"Inspection error: {exc}"]
        )

    logger.info(
        "Inspection: source_type=%s, pages=%d, tables_likely=%s",
        inspection.source_type,
        inspection.page_count,
        inspection.tables_likely,
    )

    # ------------------------------------------------------------------
    # STEP 8 branch: scanned PDF → OCR
    # ------------------------------------------------------------------

    if inspection.is_scanned:
        logger.info("Routing to OCR path (scanned PDF).")
        ocr = OCRExtractor(pdf_path)
        ocr_result = ocr.extract()

        if ocr_result["success"]:
            text_for_validation = ocr_result.get("text", "")
            status, warnings, scores = validate_extraction(
                text_for_validation, context="ocr"
            )
            result = normalise(ocr_result, inspection, status, warnings, scores)
            if result.validation.status in ("GOOD", "DEGRADED"):
                _classify_result(result)
                _extract_clinical_info(result)
        else:
            errors = ocr_result.get("errors", ["OCR extraction failed."])
            logger.error("OCR failed: %s", errors)
            result = _make_failure_result(pdf_path, inspection, "ocr", errors)

        if save_output:
            dirs = _make_output_dirs(pdf_path, output_root)
            _save_outputs(result, dirs)

        return result

    # ------------------------------------------------------------------
    # STEP 3: Digital PDF → PyMuPDF4LLM (primary)
    # ------------------------------------------------------------------

    logger.info("Routing to digital PDF path.")
    selected_result: Optional[dict] = None
    selected_text: str = ""

    primary = PyMuPDF4LLMExtractor(pdf_path)
    primary_raw = primary.extract()

    if primary_raw["success"]:
        # STEP 4: Validate
        text_for_validation = primary_raw.get("markdown", "")
        p_status, p_warnings, p_scores = validate_extraction(
            text_for_validation, context="pymupdf4llm"
        )
        logger.info("PyMuPDF4LLM validation: %s", p_status)

        if p_status == "GOOD":
            # STEP 5: Use it.
            selected_result = primary_raw
            selected_text = text_for_validation
            final_status, final_warnings, final_scores = p_status, p_warnings, p_scores
        else:
            logger.info(
                "PyMuPDF4LLM result is %s — falling back to coordinate extractor.",
                p_status,
            )
    else:
        logger.warning(
            "PyMuPDF4LLM extraction failed: %s", primary_raw.get("errors")
        )
        p_status = "FAILED"
        p_warnings = primary_raw.get("errors", [])
        p_scores = {}

    # ------------------------------------------------------------------
    # STEP 6: Fallback → coordinate extractor
    # ------------------------------------------------------------------

    if selected_result is None:
        fallback = CoordinateExtractor(pdf_path)
        fallback_raw = fallback.extract()

        if fallback_raw["success"]:
            # STEP 7: Validate
            text_for_validation = fallback_raw.get("text", "")
            f_status, f_warnings, f_scores = validate_extraction(
                text_for_validation, context="coordinate"
            )
            logger.info("Coordinate extractor validation: %s", f_status)

            selected_result = fallback_raw
            selected_text = text_for_validation
            final_status, final_warnings, final_scores = f_status, f_warnings, f_scores
        else:
            errors = (
                primary_raw.get("errors", [])
                + fallback_raw.get("errors", [])
            )
            logger.error("Both extractors failed: %s", errors)
            result = _make_failure_result(pdf_path, inspection, "none", errors)

            if save_output:
                dirs = _make_output_dirs(pdf_path, output_root)
                _save_outputs(result, dirs)

            return result

    # ------------------------------------------------------------------
    # STEP 9: Normalise
    # ------------------------------------------------------------------

    result = normalise(
        selected_result,
        inspection,
        final_status,
        final_warnings,
        final_scores,
    )

    # ------------------------------------------------------------------
    # STEP 10: Phase 2 — classify report type
    # ------------------------------------------------------------------

    if result.validation.status in ("GOOD", "DEGRADED"):
        _classify_result(result)

    # ------------------------------------------------------------------
    # STEP 11: Phase 3 — extract clinical information
    # ------------------------------------------------------------------

    if result.validation.status in ("GOOD", "DEGRADED"):
        _extract_clinical_info(result)

    # ------------------------------------------------------------------
    # STEP 12: Save outputs
    # ------------------------------------------------------------------

    if save_output:
        dirs = _make_output_dirs(pdf_path, output_root)
        _save_outputs(result, dirs)

    # ------------------------------------------------------------------
    # STEP 12: Return
    # ------------------------------------------------------------------

    logger.info(
        "Extraction complete — extractor=%s, validation=%s, "
        "sections=%d, tables=%d, measurements=%d",
        result.document.extractor,
        result.validation.status,
        len(result.sections),
        len(result.tables),
        len(result.measurements),
    )

    return result
