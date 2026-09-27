"""
ocr/__init__.py

OCR sub-package for scanned/image-only PDFs.

The OCR interface is defined here.  The full implementation is
PENDING — see interface.py for details.
"""

from extraction.ocr.interface import OCRExtractor

__all__ = ["OCRExtractor"]
