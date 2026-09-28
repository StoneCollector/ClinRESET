"""
OCR interface for scanned / image-only PDFs.

STATUS: INTERFACE DEFINED — IMPLEMENTATION PENDING
=======================================================

The OCR extraction path is intentionally separated from the digital-PDF
path so that:

1. Production processing of normal digital PDFs does not pull in
   heavyweight OCR dependencies (Tesseract, easyocr, etc.).

2. The rest of the application interacts with OCR through this clean
   interface, not through any specific OCR library directly.

3. When OCR is fully implemented it can be swapped in/out without
   changing the production pipeline.

To implement OCR
----------------
Replace the body of OCRExtractor.extract() with a real implementation.
The method must return a dict conforming to the same schema used by
PyMuPDF4LLMExtractor and CoordinateExtractor:

{
    "success":   bool,
    "extractor": "ocr",
    "pages":     [{"page": int, "text": str}, ...],
    "text":      str,
    "errors":    list[str],
}

Candidate OCR libraries
-----------------------
- pytesseract + pdf2image      (Tesseract backend)
- easyocr                      (neural, no Tesseract required)
- paddleocr                    (PaddlePaddle backend)
- azure-cognitiveservices-vision  (cloud)
- google-cloud-vision           (cloud)

Any chosen library MUST be listed in a separate requirements-ocr.txt
and MUST NOT be added to the core requirements.txt so that users who
only process digital PDFs are not forced to install OCR dependencies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OCRExtractor:
    """
    Clean OCR interface for scanned/image-only PDFs.

    The pipeline calls:

        extractor = OCRExtractor(pdf_path)
        result    = extractor.extract()

    The return value has the same schema as the digital extractors so
    that the normaliser and validator can process OCR output identically.

    IMPLEMENTATION STATUS: PENDING
    ------------------------------
    extract() currently returns a structured "not implemented" error.
    Do NOT interpret this as OCR being complete.
    """

    def __init__(self, pdf_path: str | Path) -> None:
        self.pdf_path = Path(pdf_path)

    def extract(self) -> dict[str, Any]:
        """
        Run OCR extraction on a scanned PDF.

        Returns
        -------
        Structured result dict.  When OCR is not yet implemented,
        returns success=False with a clear error message.
        """
        logger.warning(
            "OCR extraction requested for %s but OCR is not yet implemented.",
            self.pdf_path,
        )

        return {
            "success": False,
            "extractor": "ocr",
            "pages": [],
            "text": "",
            "errors": [
                "OCR extraction is not yet implemented. "
                "Scanned/image-only PDFs cannot be processed at this stage. "
                "See extraction/ocr/interface.py for implementation guidance."
            ],
        }

    @staticmethod
    def is_available() -> bool:
        """Return True when OCR dependencies are installed and ready."""
        # Update this method when the OCR implementation is complete.
        return False
