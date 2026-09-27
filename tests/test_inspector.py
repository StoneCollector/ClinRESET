"""
tests/test_inspector.py

Tests for the PDF inspector (extraction STEP 1 & 2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from extraction.inspector import PDFInspector
from tests.conftest import SAMPLE_REPORT


# ---------------------------------------------------------------------------
# File-validation errors
# ---------------------------------------------------------------------------


def test_inspector_raises_for_missing_file():
    with pytest.raises(FileNotFoundError):
        PDFInspector("/nonexistent/path.pdf").inspect()


def test_inspector_raises_for_non_pdf(tmp_path):
    txt = tmp_path / "doc.txt"
    txt.write_text("hello")
    with pytest.raises(ValueError):
        PDFInspector(txt).inspect()


# ---------------------------------------------------------------------------
# Minimal digital PDF
# ---------------------------------------------------------------------------


def test_inspector_digital_pdf(tmp_digital_pdf):
    result = PDFInspector(tmp_digital_pdf).inspect()
    assert result.page_count >= 1
    assert result.source_type == "digital_pdf"
    assert result.has_usable_text
    assert result.is_digital
    assert not result.is_scanned


# ---------------------------------------------------------------------------
# Empty / blank PDF
# ---------------------------------------------------------------------------


def test_inspector_empty_pdf(tmp_empty_pdf):
    result = PDFInspector(tmp_empty_pdf).inspect()
    assert result.page_count == 1
    # A blank PDF may be classified as unknown or scanned — should NOT be digital.
    assert result.source_type in ("unknown", "scanned_pdf")


# ---------------------------------------------------------------------------
# Multi-page PDF
# ---------------------------------------------------------------------------


def test_inspector_multipage_pdf(tmp_multipage_pdf):
    result = PDFInspector(tmp_multipage_pdf).inspect()
    assert result.page_count == 2
    assert result.source_type == "digital_pdf"
    assert len(result.chars_per_page) == 2


# ---------------------------------------------------------------------------
# Sample echocardiography report (regression)
# ---------------------------------------------------------------------------


def test_inspector_sample_report(sample_report_path):
    result = PDFInspector(sample_report_path).inspect()
    assert result.page_count == 2
    assert result.source_type == "digital_pdf"
    assert result.has_usable_text
    assert result.total_characters > 200
