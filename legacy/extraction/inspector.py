"""
PDF inspector.

STEP 1 of the production pipeline.

Determines the technical characteristics of a PDF without
performing any content extraction or medical interpretation:

- page count
- whether a usable text layer exists
- approximate text density per page
- whether pages are primarily images
- whether meaningful text can be extracted
- whether tables are likely present
- routing decision: "digital_pdf" | "scanned_pdf"

No medical interpretation is performed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pymupdf as fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Minimum characters on a page to consider it to have a usable text layer.
_MIN_CHARS_PER_PAGE = 30

# Minimum fraction of pages that must have usable text for the document to be
# classified as a digital PDF.
_MIN_TEXT_PAGE_FRACTION = 0.5

# Minimum characters in the whole document to rule out an empty/corrupt PDF.
_MIN_TOTAL_CHARS = 20

# Heuristic: if a page has a very large image block and very few characters,
# it is likely a scanned page.
_IMAGE_HEAVY_CHAR_THRESHOLD = 10


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class InspectionResult:
    """Technical characteristics of the source PDF."""

    file_name: str
    page_count: int
    source_type: str                        # "digital_pdf" | "scanned_pdf" | "unknown"
    total_characters: int = 0
    chars_per_page: list[int] = field(default_factory=list)
    pages_with_text: int = 0
    pages_image_only: int = 0
    tables_likely: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def has_usable_text(self) -> bool:
        return self.total_characters >= _MIN_TOTAL_CHARS

    @property
    def is_digital(self) -> bool:
        return self.source_type == "digital_pdf"

    @property
    def is_scanned(self) -> bool:
        return self.source_type == "scanned_pdf"


# ---------------------------------------------------------------------------
# Inspector
# ---------------------------------------------------------------------------


class PDFInspector:
    """
    Inspects a PDF to determine its technical characteristics and
    routes it to the correct extraction path.

    Usage::

        inspector = PDFInspector(pdf_path)
        result    = inspector.inspect()
    """

    def __init__(self, pdf_path: str | Path) -> None:
        self.pdf_path = Path(pdf_path)

    def inspect(self) -> InspectionResult:
        """
        Perform the inspection and return an InspectionResult.

        Raises
        ------
        FileNotFoundError
            If the PDF file does not exist.
        ValueError
            If the path does not point to a .pdf file.
        """

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {self.pdf_path}")

        logger.debug("Inspecting PDF: %s", self.pdf_path)

        result = InspectionResult(
            file_name=self.pdf_path.name,
            page_count=0,
            source_type="unknown",
        )

        try:
            with fitz.open(str(self.pdf_path)) as doc:
                result.page_count = doc.page_count
                logger.debug("Page count: %d", result.page_count)

                if result.page_count == 0:
                    result.warnings.append("PDF has zero pages.")
                    result.source_type = "unknown"
                    return result

                chars_per_page: list[int] = []
                pages_with_text = 0
                pages_image_only = 0
                tables_likely = False

                for page_idx in range(result.page_count):
                    page = doc[page_idx]
                    text = page.get_text("text")
                    char_count = len(text.strip())
                    chars_per_page.append(char_count)

                    # Check for table-like content heuristically.
                    # PyMuPDF find_tables is used only as an inspector probe.
                    if not tables_likely:
                        try:
                            finder = page.find_tables()
                            if finder.tables:
                                tables_likely = True
                        except Exception:
                            pass

                    # Determine whether this page has usable text.
                    if char_count >= _MIN_CHARS_PER_PAGE:
                        pages_with_text += 1
                    else:
                        # Check if the page is image-heavy.
                        image_list = page.get_images(full=False)
                        if image_list:
                            pages_image_only += 1
                        else:
                            # Genuinely sparse page (e.g. mostly whitespace).
                            result.warnings.append(
                                f"Page {page_idx + 1} has very few characters "
                                f"({char_count}) and no detected images."
                            )

                result.chars_per_page = chars_per_page
                result.total_characters = sum(chars_per_page)
                result.pages_with_text = pages_with_text
                result.pages_image_only = pages_image_only
                result.tables_likely = tables_likely

                # ---- Routing decision ----
                text_fraction = (
                    pages_with_text / result.page_count
                    if result.page_count > 0
                    else 0.0
                )

                if text_fraction >= _MIN_TEXT_PAGE_FRACTION:
                    result.source_type = "digital_pdf"
                elif pages_image_only > 0:
                    result.source_type = "scanned_pdf"
                else:
                    result.source_type = "unknown"
                    result.warnings.append(
                        "Could not reliably determine whether PDF is digital or scanned."
                    )

                logger.info(
                    "Inspection complete — pages=%d, source_type=%s, "
                    "pages_with_text=%d, tables_likely=%s",
                    result.page_count,
                    result.source_type,
                    pages_with_text,
                    tables_likely,
                )

        except fitz.FileDataError as exc:
            result.warnings.append(f"PyMuPDF could not open PDF: {exc}")
            result.source_type = "unknown"

        return result
