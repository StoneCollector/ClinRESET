"""
ClinRESET Parsing Package.
Provides PDF parsing, section detection, and OCR fallback.
"""

from .models import ParsedDocument, ParsedPage, Section
from .ocr import OCREngine, OCRError
from .parser import PDFParser
from .section_detector import SectionDetector

__all__ = [
    "ParsedDocument",
    "ParsedPage",
    "Section",
    "OCREngine",
    "OCRError",
    "PDFParser",
    "SectionDetector",
]
