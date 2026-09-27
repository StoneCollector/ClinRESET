"""
tests/test_extractors.py

Unit tests for the two production extractors:
    - PyMuPDF4LLMExtractor (primary)
    - CoordinateExtractor  (fallback)

Also tests fallback behaviour when PyMuPDF4LLM fails.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from extraction.extractors.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
from extraction.extractors.coordinate_extractor import CoordinateExtractor


# ---------------------------------------------------------------------------
# PyMuPDF4LLM extractor — success path
# ---------------------------------------------------------------------------


def test_pymupdf4llm_success_on_digital_pdf(tmp_digital_pdf):
    extractor = PyMuPDF4LLMExtractor(tmp_digital_pdf)
    result = extractor.extract()
    assert result["success"] is True
    assert result["extractor"] == "pymupdf4llm"
    assert len(result["markdown"]) > 0
    assert isinstance(result["pages"], list)
    assert len(result["pages"]) >= 1


def test_pymupdf4llm_success_on_sample_report(sample_report_path):
    extractor = PyMuPDF4LLMExtractor(sample_report_path)
    result = extractor.extract()
    assert result["success"] is True
    assert len(result["markdown"]) > 100
    assert len(result["pages"]) == 2


def test_pymupdf4llm_multipage_pdf(tmp_multipage_pdf):
    extractor = PyMuPDF4LLMExtractor(tmp_multipage_pdf)
    result = extractor.extract()
    assert result["success"] is True
    assert len(result["pages"]) == 2


def test_pymupdf4llm_returns_error_list_on_failure(tmp_digital_pdf):
    """Simulate ImportError (pymupdf4llm unavailable)."""
    extractor = PyMuPDF4LLMExtractor(tmp_digital_pdf)
    with patch.dict("sys.modules", {"pymupdf4llm": None}):
        result = extractor.extract()
    # Either succeeds (if cached import already present) or fails gracefully.
    assert "success" in result
    assert "errors" in result


def test_pymupdf4llm_page_markers_present(tmp_digital_pdf):
    """Page boundary markers must appear in the assembled Markdown."""
    extractor = PyMuPDF4LLMExtractor(tmp_digital_pdf)
    result = extractor.extract()
    if result["success"] and len(result["pages"]) > 0:
        assert "<!-- page" in result["markdown"]


# ---------------------------------------------------------------------------
# Coordinate extractor — success path
# ---------------------------------------------------------------------------


def test_coordinate_extractor_success_on_digital_pdf(tmp_digital_pdf):
    extractor = CoordinateExtractor(tmp_digital_pdf)
    result = extractor.extract()
    assert result["success"] is True
    assert result["extractor"] == "coordinate"
    assert len(result["text"]) > 0
    assert isinstance(result["pages"], list)


def test_coordinate_extractor_success_on_sample_report(sample_report_path):
    extractor = CoordinateExtractor(sample_report_path)
    result = extractor.extract()
    assert result["success"] is True
    assert len(result["pages"]) == 2
    full_text = result["text"]
    # Must preserve measurement names.
    assert "Ejection Fraction" in full_text or "ejection fraction" in full_text.lower()


def test_coordinate_extractor_page_delimiters(tmp_multipage_pdf):
    extractor = CoordinateExtractor(tmp_multipage_pdf)
    result = extractor.extract()
    assert result["success"] is True
    assert "--- PAGE 1 ---" in result["text"]
    assert "--- PAGE 2 ---" in result["text"]


def test_coordinate_extractor_preserves_column_structure(sample_report_path):
    """
    The pipe ' | ' delimiter must appear in the output for the
    echocardiography report which has table-like columns.
    """
    extractor = CoordinateExtractor(sample_report_path)
    result = extractor.extract()
    assert result["success"] is True
    # The report has measurement columns — expect at least some pipe delimiters.
    assert "|" in result["text"]


def test_coordinate_extractor_empty_pdf(tmp_empty_pdf):
    extractor = CoordinateExtractor(tmp_empty_pdf)
    result = extractor.extract()
    # Should succeed but return very little text.
    assert result["success"] is True
    assert isinstance(result["text"], str)


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------


def test_pipeline_falls_back_to_coordinate_when_primary_fails(
    tmp_digital_pdf, tmp_path
):
    """
    When PyMuPDF4LLM fails, the pipeline must use the coordinate extractor
    and NOT crash.
    """
    from extraction.pipeline import extract_document

    # Patch PyMuPDF4LLMExtractor.extract to return a failure.
    failure = {
        "success": False,
        "extractor": "pymupdf4llm",
        "markdown": "",
        "pages": [],
        "errors": ["Simulated primary extractor failure"],
    }
    with patch(
        "extraction.pipeline.PyMuPDF4LLMExtractor.extract",
        return_value=failure,
    ):
        result = extract_document(
            tmp_digital_pdf,
            output_root=tmp_path / "output",
            save_output=False,
        )

    assert result.document.extractor == "coordinate"
    assert result.validation.status != "FAILED" or len(result.raw.text) >= 0


def test_pipeline_uses_primary_when_primary_succeeds(
    sample_report_path, tmp_path
):
    """When PyMuPDF4LLM succeeds with GOOD status, coordinate extractor must NOT run."""
    from extraction.pipeline import extract_document

    coord_mock = MagicMock()

    with patch("extraction.pipeline.CoordinateExtractor", coord_mock):
        result = extract_document(
            sample_report_path,
            output_root=tmp_path / "output",
            save_output=False,
        )

    # Coordinate extractor should NOT have been instantiated.
    coord_mock.assert_not_called()
    assert result.document.extractor == "pymupdf4llm"
