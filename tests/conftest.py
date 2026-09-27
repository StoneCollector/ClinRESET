"""
tests/conftest.py

Shared fixtures and helpers for the extraction-layer test suite.
"""

from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path
from typing import Generator

import pymupdf as fitz
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SAMPLE_REPORT = Path(__file__).parent.parent / "txt_extractor" / "sample_report.pdf"
OUTPUT_ROOT = Path(__file__).parent.parent / "output"


# ---------------------------------------------------------------------------
# PDF factory helpers
# ---------------------------------------------------------------------------


def make_minimal_digital_pdf(text: str = "Hello World\nTest line 2") -> bytes:
    """Return a minimal digital (text-layer) PDF as bytes."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_minimal_table_pdf(rows: list[list[str]]) -> bytes:
    """Return a PDF whose content resembles a table."""
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for row in rows:
        line = "   ".join(row)
        page.insert_text((72, y), line, fontsize=11)
        y += 20
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_empty_pdf() -> bytes:
    """Return a valid PDF with one blank (no-text) page."""
    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_multipage_pdf(pages: list[str]) -> bytes:
    """Return a PDF with one text block per page."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_report_path() -> Path:
    """Path to the real echocardiography sample report."""
    if not SAMPLE_REPORT.exists():
        pytest.skip(f"Sample report not found: {SAMPLE_REPORT}")
    return SAMPLE_REPORT


@pytest.fixture()
def tmp_digital_pdf(tmp_path: Path) -> Path:
    """A temporary minimal digital PDF."""
    pdf_bytes = make_minimal_digital_pdf(
        "Patient Report\n\nHaemoglobin: 13.5 g/dL (12-16)\nWBC: 7.2 10^3/uL (4-11)"
    )
    p = tmp_path / "digital.pdf"
    p.write_bytes(pdf_bytes)
    return p


@pytest.fixture()
def tmp_empty_pdf(tmp_path: Path) -> Path:
    """A temporary PDF with a blank page (no text)."""
    p = tmp_path / "empty.pdf"
    p.write_bytes(make_empty_pdf())
    return p


@pytest.fixture()
def tmp_multipage_pdf(tmp_path: Path) -> Path:
    """A temporary multi-page PDF."""
    pages = [
        "ECHO CARDIOGRAPHY REPORT\nPatient: Test",
        "Doppler findings\nNo regurgitation\nFINAL IMPRESSION:\nNormal study",
    ]
    p = tmp_path / "multipage.pdf"
    p.write_bytes(make_multipage_pdf(pages))
    return p


@pytest.fixture()
def tmp_table_pdf(tmp_path: Path) -> Path:
    """A temporary table-heavy PDF."""
    rows = [
        ["MEASUREMENT", "VALUE", "NORMAL VALUES"],
        ["Haemoglobin", "13.5", "12-16 g/dL"],
        ["WBC", "7.2", "4-11 10^3/uL"],
        ["Platelet", "250", "150-400 10^3/uL"],
    ]
    p = tmp_path / "table.pdf"
    p.write_bytes(make_minimal_table_pdf(rows))
    return p
