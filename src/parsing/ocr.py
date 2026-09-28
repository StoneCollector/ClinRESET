"""
OCR Engine and fallback utilities for scanned or image-based PDF pages.
Uses PyMuPDF in-memory rendering and pytesseract.
"""

import os
import shutil
import logging
from typing import Optional
from PIL import Image
import pymupdf

logger = logging.getLogger(__name__)

class OCRError(Exception):
    """Raised when OCR extraction fails or OCR engine is unavailable."""
    pass


class OCREngine:
    def __init__(self, tesseract_cmd: Optional[str] = None):
        if tesseract_cmd is None:
            tesseract_cmd = os.environ.get("TESSERACT_CMD")
        if tesseract_cmd is None:
            tesseract_cmd = shutil.which("tesseract")

        self.tesseract_cmd = tesseract_cmd
        self._available = False
        if self.tesseract_cmd and os.path.exists(self.tesseract_cmd):
            self._available = True
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            except Exception as e:
                logger.warning(f"Could not initialize pytesseract with {self.tesseract_cmd}: {e}")
                self._available = False
        else:
            # Check default import
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self._available = True
            except Exception:
                self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def render_page_to_image(self, page: pymupdf.Page, dpi: int = 300) -> Image.Image:
        """Renders a PDF page to a PIL Image at specified DPI directly in memory."""
        zoom = dpi / 72.0
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img

    def extract_text_from_page(self, page: pymupdf.Page) -> str:
        """Runs OCR on a PDF page."""
        if not self.is_available:
            raise OCRError(
                "Tesseract OCR is not installed or not found in PATH/TESSERACT_CMD. "
                "Please install Tesseract and set TESSERACT_CMD in your environment."
            )
        import pytesseract
        img = self.render_page_to_image(page)
        text = pytesseract.image_to_string(img)
        return text
