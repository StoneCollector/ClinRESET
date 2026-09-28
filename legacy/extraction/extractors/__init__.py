"""
extractors/__init__.py

Exposes the two production extractors.

Production extraction order (fixed):
    1. PyMuPDF4LLMExtractor  — primary
    2. CoordinateExtractor   — deterministic fallback
"""

from extraction.extractors.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
from extraction.extractors.coordinate_extractor import CoordinateExtractor

__all__ = ["PyMuPDF4LLMExtractor", "CoordinateExtractor"]
