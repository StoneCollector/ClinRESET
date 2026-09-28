"""
Primary digital PDF extractor — PyMuPDF4LLM.

This is STEP 3 of the production pipeline for digital PDFs.

PyMuPDF4LLM produces Markdown-oriented output that preserves:
- headings / hierarchy
- paragraphs
- lists
- pipe-delimited tables (critical for medical measurement rows)
- page boundaries via page_chunks=True

The raw Markdown is never immediately flattened to plain text.
It is retained in the ExtractionResult.raw.markdown field so that
downstream components can parse it precisely.

No medical interpretation is performed here.
"""

from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PyMuPDF4LLMExtractor:
    """
    Wraps pymupdf4llm to extract Markdown from a digital PDF.

    Usage::

        extractor = PyMuPDF4LLMExtractor(pdf_path)
        result    = extractor.extract()
        # result["success"]  → bool
        # result["markdown"] → str
        # result["pages"]    → list[dict]  (per-page chunks)
        # result["errors"]   → list[str]
    """

    def __init__(self, pdf_path: str | Path) -> None:
        self.pdf_path = Path(pdf_path)

    def extract(self) -> dict[str, Any]:
        """
        Run PyMuPDF4LLM extraction.

        Returns a structured dict so that failures are always explicit
        and the pipeline can decide whether to fall back.

        Returns
        -------
        {
            "success":  bool,
            "extractor": "pymupdf4llm",
            "markdown": str,        # full document Markdown
            "pages":    list[dict], # per-page chunk dicts
            "errors":   list[str],
        }
        """
        logger.info("Running PyMuPDF4LLM extractor on: %s", self.pdf_path)

        result: dict[str, Any] = {
            "success": False,
            "extractor": "pymupdf4llm",
            "markdown": "",
            "pages": [],
            "errors": [],
        }

        try:
            import pymupdf4llm  # noqa: PLC0415

            # page_chunks=True returns a list of dicts, one per page.
            # Each chunk contains "text" (Markdown) and "metadata" with page info.
            page_chunks: list[dict] = pymupdf4llm.to_markdown(
                str(self.pdf_path),
                page_chunks=True,
            )

            if not page_chunks:
                result["errors"].append("pymupdf4llm returned an empty page list.")
                logger.warning("pymupdf4llm returned empty output for %s", self.pdf_path)
                return result

            result["pages"] = page_chunks

            # Assemble the full Markdown with page-boundary markers so that
            # page traceability is preserved in the combined string.
            parts: list[str] = []
            for chunk in page_chunks:
                meta = chunk.get("metadata", {})
                # pymupdf4llm uses 'page_number' (1-indexed) in chunk metadata.
                page_num = meta.get("page_number", meta.get("page", None))
                page_text = chunk.get("text", "")
                if page_num is not None:
                    parts.append(f"\n<!-- page {page_num} -->\n")
                parts.append(page_text)

            result["markdown"] = "".join(parts)
            result["success"] = True

            logger.info(
                "PyMuPDF4LLM extraction successful — %d pages, %d chars",
                len(page_chunks),
                len(result["markdown"]),
            )

        except ImportError:
            msg = "pymupdf4llm is not installed. Run: pip install pymupdf4llm"
            result["errors"].append(msg)
            logger.error(msg)

        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            result["errors"].append(msg)
            logger.error("PyMuPDF4LLM extraction failed: %s", msg)
            logger.debug("Traceback:\n%s", traceback.format_exc())

        return result
