"""
classification/signal_extractor.py

Extracts classifiable signals from an ExtractionResult.

The signal extractor bridges Phase 1 output and the classifier.
It converts the structured ExtractionResult into a flat list of
SignalCandidate objects, each carrying:

  - the raw matched text
  - which field it came from (document title, section title, etc.)
  - the page number (for traceability)
  - the section context (for traceability)

The classifier then tests each SignalCandidate against every report
signature without needing to know the ExtractionResult structure.

Design rules
------------
- No PDF re-processing.
- No text generation or fabrication.
- All signals are derived directly from ExtractionResult fields.
- Raw text is used as a LAST RESORT fallback after structured signals.
- Signal text is preserved exactly as extracted (including formatting
  characters like ** or <u>) so that the evidence log is traceable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from extraction.models import ExtractionResult


# ---------------------------------------------------------------------------
# Signal candidate
# ---------------------------------------------------------------------------


@dataclass
class SignalCandidate:
    """
    A single piece of text from the document available for matching.

    Attributes
    ----------
    text:
        The extracted text, preserved as-is from the ExtractionResult.
    source_field:
        The structural origin of this text:
            "document_title"   — inferred from first non-null section title
            "section_title"    — from Section.title
            "table_title"      — from Table.title
            "table_header"     — from Table.headers entries
            "measurement_name" — from Measurement.name
            "section_text"     — from Section.text (body, lower priority)
            "raw_text"         — from ExtractionResult.raw.text (last resort)
    page:
        Page number if available (1-indexed).
    section_context:
        The title of the section this signal lives in, if applicable.
    """

    text: str
    source_field: str
    page: Optional[int] = None
    section_context: Optional[str] = None


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------


def _strip_markup(text: str) -> str:
    """
    Remove Markdown formatting and HTML tags, returning clean text.

    Preserves the underlying words; does not alter alphanumeric content.
    Used only for matching purposes — the original text is always stored
    in SignalCandidate.text for traceability.
    """
    # Remove HTML tags (<u>, <br>, etc.)
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove Markdown bold/italic markers
    text = re.sub(r"\*{1,3}", "", text)
    text = re.sub(r"_{1,3}", "", text)
    # Remove Markdown heading markers
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _infer_document_title(result: ExtractionResult) -> Optional[str]:
    """
    Attempt to identify the document-level title.

    Strategy (in order):
    1. First non-null section title that contains at least one word
       of length ≥ 3 and is not a patient-info line.
    2. None if no suitable candidate found.

    The document title is the highest-priority signal: a direct title
    match carries the maximum weight.
    """
    patient_info_patterns = re.compile(
        r"\b(NAME|AGE|SEX|REF|DATE|DATED|IPD|OPD|MRN|DOB)\b",
        re.IGNORECASE,
    )

    for section in result.sections:
        raw_title = section.title
        if not raw_title:
            continue
        clean = _strip_markup(raw_title)
        if not clean:
            continue
        # Skip patient-header lines.
        if patient_info_patterns.search(clean):
            continue
        # Must have at least one substantial word.
        if any(len(w) >= 3 for w in clean.split()):
            return clean  # Return first plausible title

    return None


def extract_signals(result: ExtractionResult) -> list[SignalCandidate]:
    """
    Convert an ExtractionResult into a flat list of SignalCandidates.

    Signal priority order (matches classifier preference):
    1. Document title (inferred)
    2. Section titles
    3. Table titles + table headers
    4. Measurement names
    5. Section body text (paragraphs)
    6. Raw text (fallback, used only if no structured signals exist)

    Returns
    -------
    list[SignalCandidate]
        All extracted signals, in priority order.
    """
    signals: list[SignalCandidate] = []

    # ------------------------------------------------------------------
    # 1. Document title
    # ------------------------------------------------------------------
    doc_title = _infer_document_title(result)
    if doc_title:
        signals.append(SignalCandidate(
            text=doc_title,
            source_field="document_title",
            page=result.sections[0].page if result.sections else None,
            section_context=None,
        ))

    # ------------------------------------------------------------------
    # 2. Section titles
    # ------------------------------------------------------------------
    for section in result.sections:
        if not section.title:
            continue
        clean_title = _strip_markup(section.title)
        if not clean_title:
            continue
        signals.append(SignalCandidate(
            text=clean_title,
            source_field="section_title",
            page=section.page,
            section_context=clean_title,
        ))

    # ------------------------------------------------------------------
    # 3. Table titles and column headers
    # ------------------------------------------------------------------
    for table in result.tables:
        if table.title:
            clean_ttitle = _strip_markup(table.title)
            if clean_ttitle:
                signals.append(SignalCandidate(
                    text=clean_ttitle,
                    source_field="table_title",
                    page=table.page,
                    section_context=clean_ttitle,
                ))

        for header in table.headers:
            if not header:
                continue
            clean_hdr = _strip_markup(header)
            if clean_hdr:
                signals.append(SignalCandidate(
                    text=clean_hdr,
                    source_field="table_header",
                    page=table.page,
                    section_context=table.title,
                ))

    # ------------------------------------------------------------------
    # 4. Measurement names
    # ------------------------------------------------------------------
    for measurement in result.measurements:
        if not measurement.name:
            continue
        signals.append(SignalCandidate(
            text=measurement.name,
            source_field="measurement_name",
            page=measurement.page,
            section_context=measurement.source_section,
        ))

    # ------------------------------------------------------------------
    # 5. Section body text (split into lines for granular matching)
    # ------------------------------------------------------------------
    for section in result.sections:
        if not section.text:
            continue
        clean_body = _strip_markup(section.text)
        if not clean_body:
            continue
        # Add the whole body as one signal (for multi-word phrase matching).
        signals.append(SignalCandidate(
            text=clean_body,
            source_field="section_text",
            page=section.page,
            section_context=section.title,
        ))

    # ------------------------------------------------------------------
    # 6. Raw text fallback
    #    Only added if no structured signals were produced (e.g. the
    #    extraction result has no parsed sections/tables/measurements).
    # ------------------------------------------------------------------
    structured_count = (
        len(result.sections) + len(result.tables) + len(result.measurements)
    )
    if structured_count == 0 and result.raw.text:
        signals.append(SignalCandidate(
            text=result.raw.text,
            source_field="raw_text",
            page=None,
            section_context=None,
        ))

    return signals
