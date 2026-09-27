"""
Extraction layer for the ClinRESET NLP pipeline.

This package implements the document extraction layer that converts
medical PDFs into a clean, structured, traceable intermediate
representation (normalized JSON).

Production extraction order (fixed):
    1. PDF inspection  →  digital vs scanned
    2. digital PDF     →  PyMuPDF4LLM (primary)
    3. validation      →  GOOD / DEGRADED / FAILED
    4. DEGRADED/FAILED →  coordinate extractor (fallback)
    5. validation
    6. scanned PDF     →  OCR interface (pending full implementation)

Out of scope:
    report classification, clinical NER, abnormality detection,
    patient-facing simplification, and any form of medical inference.
"""

from extraction.pipeline import extract_document
from extraction.models import ExtractionResult

__all__ = ["extract_document", "ExtractionResult"]
