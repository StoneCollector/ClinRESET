"""
Main PDF Parser for ClinRESET.
Orchestrates digital extraction (PyMuPDF) with OCR fallback and section detection.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import pymupdf

from .models import ParsedDocument, ParsedPage, Section
from .section_detector import SectionDetector
from .ocr import OCREngine, OCRError

logger = logging.getLogger(__name__)

class PDFParser:
    """Robust PDF report parser with digital extraction and OCR fallback."""

    def __init__(self, ocr_engine: Optional[OCREngine] = None, min_char_threshold: int = 40):
        self.ocr_engine = ocr_engine or OCREngine()
        self.min_char_threshold = min_char_threshold

    def parse(self, pdf_path: str | Path) -> ParsedDocument:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

        try:
            doc = pymupdf.open(str(pdf_path))
        except Exception as e:
            raise ValueError(f"Failed to open PDF {pdf_path}: {e}")

        pages: List[ParsedPage] = []
        all_sections: List[Section] = []
        full_text_parts: List[str] = []
        methods_used = set()

        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1
            # 1. Digital text extraction
            raw_text = page.get_text() or ""
            method = "digital"

            # 2. Check if text is sparse or image-only
            clean_text = raw_text.strip()
            if len(clean_text) < self.min_char_threshold:
                if self.ocr_engine.is_available:
                    try:
                        logger.info(f"Page {page_num} of {pdf_path.name} is sparse ({len(clean_text)} chars). Triggering OCR.")
                        ocr_text = self.ocr_engine.extract_text_from_page(page)
                        if len(ocr_text.strip()) > len(clean_text):
                            raw_text = ocr_text
                            method = "ocr"
                    except Exception as e:
                        logger.warning(f"OCR failed on page {page_num} of {pdf_path.name}: {e}")
                else:
                    logger.debug(f"Page {page_num} sparse, but OCR engine is unavailable.")

            methods_used.add(method)
            char_count = len(raw_text)
            full_text_parts.append(raw_text)

            # 3. Detect sections on page
            page_sections = SectionDetector.detect_sections(raw_text, page_number=page_num)
            all_sections.extend(page_sections)

            pages.append(ParsedPage(
                page_number=page_num,
                raw_text=raw_text,
                char_count=char_count,
                extraction_method=method,
                sections=page_sections
            ))

        doc.close()

        # Overall method
        if len(methods_used) > 1:
            overall_method = "hybrid"
        elif "ocr" in methods_used:
            overall_method = "ocr"
        else:
            overall_method = "digital"

        full_text = "\n\n".join(full_text_parts)
        metadata = self._extract_header_metadata(all_sections)

        return ParsedDocument(
            file_path=str(pdf_path),
            file_name=pdf_path.name,
            page_count=len(pages),
            full_text=full_text,
            extraction_method=overall_method,
            pages=pages,
            sections=all_sections,
            metadata=metadata
        )

    def _extract_header_metadata(self, sections: List[Section]) -> Dict[str, Any]:
        """Extracts patient metadata from header/demographic sections."""
        metadata = {
            "patient_name": None,
            "patient_id": None,
            "age": None,
            "sex": None,
            "date": None,
            "ref_by": None
        }

        # Search the first couple of sections
        header_text = ""
        for s in sections[:3]:
            header_text += "\n" + s.content

        # Name / ID
        m_id = re.search(r"\bPatient\s+ID\s*[:.-]?\s*([A-Za-z0-9_]+)", header_text, re.IGNORECASE)
        if m_id:
            metadata["patient_id"] = m_id.group(1).strip()

        m_name = re.search(r"\b(?:Patient\s+)?NAME\s*[:.-]?\s*([A-Za-z0-9_\s.]+?)(?=\s{2,}|\bAGE|\bDATED|\bDATE|\bREF|$|\n)", header_text, re.IGNORECASE)
        if m_name:
            val = m_name.group(1).strip()
            if val and len(val) < 50:
                metadata["patient_name"] = val

        # Age
        m_age = re.search(r"\bAGE(?:/SEX)?\s*[:.-]?\s*([0-9]+\s*(?:y|yrs|years)?)\b", header_text, re.IGNORECASE)
        if m_age:
            metadata["age"] = m_age.group(1).strip()

        # Sex / Gender
        m_sex = re.search(r"\b(?:SEX|GENDER)\s*[:.-]?\s*([MF]|Male|Female)\b", header_text, re.IGNORECASE)
        if m_sex:
            metadata["sex"] = m_sex.group(1).strip()

        # Date
        m_date = re.search(r"\b(?:DATE|DATED)\s*[:.-]?\s*([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})", header_text, re.IGNORECASE)
        if m_date:
            metadata["date"] = m_date.group(1).strip()

        # Referring Doctor
        m_ref = re.search(r"\bREF(?:\.|ERRED)?\s*BY\s*[:.-]?\s*([A-Za-z0-9_\s.]+?)(?=\n|$|\s{2,})", header_text, re.IGNORECASE)
        if m_ref:
            metadata["ref_by"] = m_ref.group(1).strip()

        return metadata
