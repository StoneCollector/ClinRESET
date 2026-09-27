"""
Deterministic fallback digital-PDF extractor — coordinate-based.

This is STEP 6 of the production pipeline (triggered only when
PyMuPDF4LLM produces a DEGRADED or FAILED result).

Implementation is adapted from the project's existing
txt_extractor/text_extractor_v2.py (MedicalReportExtractor), which
was experimentally validated on the sample echocardiography report.

Key technique
-------------
page.get_text("words", sort=True) returns every PDF word with its
bounding-box coordinates (x0, y0, x1, y1).  Words that share a
similar Y-centre are grouped into a single visual line.  Words within
a line that are separated by a large horizontal gap are delimited with
" | " to signal a column boundary.

This reconstructs table-like relationships such as:

    Ejection Fraction | 60 % | (55-74%)

without interpreting the medical meaning of those values.

No medical inference is performed here.
"""

from __future__ import annotations

import logging
import re
import traceback
from pathlib import Path
from typing import Any

import pymupdf as fitz

logger = logging.getLogger(__name__)

# Horizontal gap (points) above which two adjacent words are treated as
# being in different columns.  Validated on the sample echocardiography
# report; adjust if other report layouts require it.
_COLUMN_GAP_THRESHOLD = 25.0

# Y-coordinate tolerance (points) for grouping words onto the same line.
_LINE_Y_TOLERANCE = 3.0


class CoordinateExtractor:
    """
    Fallback extractor using PyMuPDF word-coordinate reconstruction.

    Adapted from txt_extractor/text_extractor_v2.py without modifying
    the original file.

    Usage::

        extractor = CoordinateExtractor(pdf_path)
        result    = extractor.extract()
        # result["success"] → bool
        # result["pages"]   → list[dict]  (per-page text)
        # result["text"]    → str         (full concatenated text)
        # result["errors"]  → list[str]
    """

    def __init__(self, pdf_path: str | Path) -> None:
        self.pdf_path = Path(pdf_path)

    # ------------------------------------------------------------------
    # Internal helpers  (adapted from MedicalReportExtractor v2)
    # ------------------------------------------------------------------

    @staticmethod
    def _group_words_into_lines(
        words: list[tuple],
        y_tolerance: float = _LINE_Y_TOLERANCE,
    ) -> list[dict]:
        """
        Group PDF words into visual lines using their Y coordinates.

        PyMuPDF returns words as:
            (x0, y0, x1, y1, text, block_no, line_no, word_no)

        Words whose Y-centres differ by less than *y_tolerance* are
        placed on the same line.  Lines are returned in top-to-bottom,
        left-to-right reading order.
        """
        if not words:
            return []

        lines: list[dict] = []

        for word in words:
            x0, y0, x1, y1, text = word[:5]
            y_center = (y0 + y1) / 2.0

            matching_line = None
            for line in lines:
                if abs(y_center - line["y_center"]) <= y_tolerance:
                    matching_line = line
                    break

            if matching_line is None:
                lines.append({"y_center": y_center, "words": [word]})
            else:
                matching_line["words"].append(word)

        for line in lines:
            line["words"].sort(key=lambda w: w[0])

        lines.sort(key=lambda l: l["y_center"])
        return lines

    @staticmethod
    def _line_to_text(words: list[tuple]) -> str:
        """
        Convert a list of positioned words into readable text.

        A horizontal gap larger than _COLUMN_GAP_THRESHOLD is rendered
        as " | " to signal a column boundary (critical for tables).
        All other gaps become a single space.
        """
        if not words:
            return ""

        result = words[0][4]
        previous_x1 = words[0][2]

        for word in words[1:]:
            x0, _, _, _, text = word[:5]
            gap = x0 - previous_x1
            if gap > _COLUMN_GAP_THRESHOLD:
                result += " | " + text
            else:
                result += " " + text
            previous_x1 = word[2]

        return result.strip()

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Basic text cleaning that preserves medical-report structure.
        Adapted from MedicalReportExtractor.clean_text().
        """
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u00a0", " ")          # non-breaking space
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" *\n *", "\n", text)
        return text.strip()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract(self) -> dict[str, Any]:
        """
        Run coordinate-based extraction.

        Returns a structured dict so that failures are always explicit.

        Returns
        -------
        {
            "success":   bool,
            "extractor": "coordinate",
            "pages":     list[{"page": int, "text": str}],
            "text":      str,   # full document text (page-delimited)
            "errors":    list[str],
        }
        """
        logger.info("Running coordinate extractor on: %s", self.pdf_path)

        result: dict[str, Any] = {
            "success": False,
            "extractor": "coordinate",
            "pages": [],
            "text": "",
            "errors": [],
        }

        try:
            with fitz.open(str(self.pdf_path)) as doc:
                pages_output: list[dict] = []

                for page_idx in range(doc.page_count):
                    page = doc[page_idx]
                    page_number = page_idx + 1

                    words = page.get_text("words", sort=True)
                    lines = self._group_words_into_lines(words)

                    text_lines: list[str] = []
                    for line in lines:
                        line_text = self._line_to_text(line["words"])
                        if line_text:
                            text_lines.append(line_text)

                    raw_text = "\n".join(text_lines)
                    cleaned = self._clean_text(raw_text)

                    pages_output.append({
                        "page": page_number,
                        "text": cleaned,
                    })

            result["pages"] = pages_output

            # Build the full text with page-boundary markers.
            full_parts: list[str] = []
            for p in pages_output:
                full_parts.append(f"\n--- PAGE {p['page']} ---\n")
                full_parts.append(p["text"])

            result["text"] = "\n".join(full_parts).strip()
            result["success"] = True

            logger.info(
                "Coordinate extraction successful — %d pages, %d chars",
                len(pages_output),
                len(result["text"]),
            )

        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            result["errors"].append(msg)
            logger.error("Coordinate extraction failed: %s", msg)
            logger.debug("Traceback:\n%s", traceback.format_exc())

        return result
