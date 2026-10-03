"""
clinical_extraction/filters.py

Centralised filtering and validation for extracted clinical measurements and findings.

This module implements:
  1. Metadata / Administrative field blocklist — reject non-clinical fields
     like "Registered on", "Collected on", "UHID", etc.
  2. Date-pattern value/unit rejection — catch fields parsed from dates
     like value=28, unit=/10/2024.
  3. Section-aware classification — identify metadata / non-clinical sections
     so extractors can skip them.
  4. Finding quality gate — reject findings that are multi-sentence paragraphs
     or that don't match a concise clinical term limit.
  5. Interpretation / explanatory section exclusion — sections whose titles
     indicate educational / commentary prose.
"""

from __future__ import annotations

import re
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Metadata field blocklist
# ---------------------------------------------------------------------------

# Field names that are NEVER clinical measurements regardless of numeric value.
# Matched case-insensitively against the stripped measurement name.
_ADMIN_FIELD_NAMES: frozenset[str] = frozenset({
    # Timestamps and registration
    "registered on", "collected on", "received on", "reported on",
    "sample collected on", "registered", "sample collected at",
    "generated on", "collection date", "report date", "test date",
    # Patient demographics / identifiers
    "uhid", "reg. no.", "reg no", "pid", "patient id", "lab id",
    "barcode", "tat", "sample id", "accession no", "accession number",
    "ref. by", "ref by", "referred by", "dr", "consultant",
    # Administrative numbers / page markers
    "page", "page no", "srno", "sr no", "s no", "sno", "serial no",
    "sl no", "sl. no.", "id", "no", "number", "visit",
    # Generic date components that get extracted by mistake
    "date", "time", "month", "year", "day",
    # Lab QC artefacts
    "normal", "normal value", "normal values", "normal range",
    "method", "methodology", "technique", "instrument",
    "lab technician", "pathologist", "doctor", "physician",
    "sample type", "primary sample type", "sample", "specimen",
})

# Regex patterns for detecting date-like values in the name field.
_DATE_WORD_PATTERN = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"january|february|march|april|june|july|august|september|"
    r"october|november|december|monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday)\b",
    re.IGNORECASE,
)

# Regex to detect date-formatted unit strings like "/10/2024", "PM", "AM", etc.
_DATE_UNIT_PATTERN = re.compile(
    r"^(/\d{1,2}/\d{2,4}|am|pm|\d{4}|pm\s*\d|am\s*\d)$",
    re.IGNORECASE,
)

# Patterns in the *value string* that suggest it is a date/time component.
_DATE_VALUE_PATTERN = re.compile(
    r"^\d{1,2}$"  # bare day number like 28, 3, 4 without medical context
)


# ---------------------------------------------------------------------------
# Interpretation / explanatory section titles
# ---------------------------------------------------------------------------

_EXPLANATORY_SECTION_TITLES: frozenset[str] = frozenset({
    "interpretation", "comment", "comments", "remark", "remarks",
    "note", "notes", "observation", "observations", "conclusion",
    "conclusions", "impression", "impressions", "advice", "recommendation",
    "recommendations", "clinical note", "clinical notes",
    "pathologist note", "lab note", "attending note",
    # Specific to format reports
    "increased in", "decreased in", "significance", "about this test",
    "about", "what does it mean", "reference",
})


# ---------------------------------------------------------------------------
# Metadata section title keywords
# ---------------------------------------------------------------------------

_METADATA_SECTION_TITLE_WORDS: frozenset[str] = frozenset({
    "patient", "demographics", "registration", "lab details",
    "laboratory details", "sample details", "specimen details",
    "report details", "contact", "footer", "header",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_admin_field(name: str) -> bool:
    """
    Return True if the measurement name is an administrative/metadata field
    that should never be shown as a clinical measurement.

    Parameters
    ----------
    name : str
        The raw measurement name extracted from the document.

    Returns
    -------
    bool
    """
    if not name:
        return True
    # Strip trailing/leading punctuation, spaces, and dots then lowercase
    clean = re.sub(r"[\.\:\;\,\s]+$", "", name.strip()).lower()
    clean = re.sub(r"^[\.\:\;\,\s]+", "", clean)
    # Also try with all dots/spaces collapsed for matching "reg. no." → "reg no"
    collapsed = re.sub(r"[\.\s]+", " ", clean).strip()
    return clean in _ADMIN_FIELD_NAMES or collapsed in _ADMIN_FIELD_NAMES


def is_date_artefact(name: str, value: Any, unit: Optional[str]) -> bool:
    """
    Return True when the combination of name / value / unit looks like a date
    component accidentally parsed as a measurement.

    Common patterns we catch:
      - name="Registered on",  value=28, unit="/10/2024"
      - name="Generated on",   value=2,  unit="Dec"
      - name="Collected on",   value=3,  unit=None  (bare day number)

    Parameters
    ----------
    name  : raw field name
    value : parsed value (int, float, or str)
    unit  : parsed unit string or None

    Returns
    -------
    bool
    """
    name_lower = (name or "").strip().lower()

    # If the name itself contains a date word ("generated on", "reported on") …
    if _DATE_WORD_PATTERN.search(name_lower):
        return True

    # If the name contains "on" near the end (a very common date-field indicator)
    if re.search(r"\bon\b", name_lower):
        return True

    # If the unit is a date fragment ("/10/2024", "PM", "Dec", …)
    if unit and _DATE_UNIT_PATTERN.match(unit.strip()):
        return True

    # If unit is a month abbreviation/name
    if unit and _DATE_WORD_PATTERN.match(unit.strip()):
        return True

    # If value is a bare day-number (1–31) and the name doesn't sound clinical
    if isinstance(value, int) and 1 <= value <= 31:
        # Only flag if name also sounds like a date field
        date_name_words = {"registered", "collected", "received", "reported",
                           "generated", "date", "day", "time", "on"}
        name_words = set(name_lower.split())
        if name_words & date_name_words:
            return True

    return False


def is_metadata_section(title: Optional[str]) -> bool:
    """
    Return True if the section title suggests patient demographics,
    registration metadata, or lab administrative content.

    Parameters
    ----------
    title : section title string, or None

    Returns
    -------
    bool
    """
    if not title:
        return False
    clean = title.strip().lower()
    # Direct match
    if clean in _METADATA_SECTION_TITLE_WORDS:
        return True
    # Keyword-in-title check
    for word in _METADATA_SECTION_TITLE_WORDS:
        if word in clean:
            return True
    return False


def is_explanatory_section(title: Optional[str]) -> bool:
    """
    Return True if the section title indicates that the content is explanatory /
    educational prose (e.g., "Interpretation", "Comment", "Remarks").

    Parameters
    ----------
    title : section title string, or None

    Returns
    -------
    bool
    """
    if not title:
        return False
    clean = title.strip().lower()
    return clean in _EXPLANATORY_SECTION_TITLES


def is_valid_finding_text(text: str, max_words: int = 10) -> bool:
    """
    Return True when *text* looks like a concise, standalone clinical finding
    (e.g. "mild anemia", "normocytic normochromic") and False when it is a
    long multi-sentence paragraph or contains only generic / non-medical words.

    Parameters
    ----------
    text     : the finding text candidate
    max_words: maximum number of words allowed in a valid finding

    Returns
    -------
    bool
    """
    if not text:
        return False

    stripped = text.strip()

    # Reject empty strings
    if len(stripped) < 3:
        return False

    # Reject multi-sentence paragraphs
    sentence_endings = len(re.findall(r"[.!?]\s+[A-Z]", stripped))
    if sentence_endings >= 2:
        return False

    # Reject anything over max_words
    word_count = len(stripped.split())
    if word_count > max_words:
        return False

    # Reject if it contains a pipe character (table cell artefact)
    if "|" in stripped:
        return False

    # Reject if it starts with a number (likely a table row artefact)
    if re.match(r"^\d", stripped):
        return False

    return True


def filter_measurements(measurements: list[Any]) -> list[Any]:
    """
    Filter a list of ClinicalMeasurement objects (or dicts), removing any that
    are administrative metadata, date artefacts, or otherwise non-clinical.

    Parameters
    ----------
    measurements : list of ClinicalMeasurement objects or dicts

    Returns
    -------
    list of valid clinical measurements
    """
    valid = []
    for m in measurements:
        # Support both dataclass and dict access
        if isinstance(m, dict):
            name = m.get("name") or ""
            value = m.get("value")
            unit = m.get("unit")
        else:
            name = getattr(m, "name", "") or ""
            value = getattr(m, "value", None)
            unit = getattr(m, "unit", None)

        if is_admin_field(name):
            continue
        if is_date_artefact(name, value, unit):
            continue
        valid.append(m)
    return valid


def filter_findings(findings: list[Any], max_words: int = 10) -> list[Any]:
    """
    Filter a list of ClinicalFinding objects (or dicts), removing any that are
    multi-sentence paragraphs or don't pass the concise-finding quality gate.

    Parameters
    ----------
    findings  : list of ClinicalFinding objects or dicts
    max_words : max words allowed in a valid finding

    Returns
    -------
    list of valid clinical findings
    """
    valid = []
    for f in findings:
        if isinstance(f, dict):
            text = f.get("text") or f.get("concept") or ""
        else:
            text = getattr(f, "text", "") or ""

        if is_valid_finding_text(text, max_words=max_words):
            valid.append(f)
    return valid
