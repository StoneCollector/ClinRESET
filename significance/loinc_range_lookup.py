"""
significance/loinc_range_lookup.py

LOINC + FHIR R4 reference range resolver.

Resolves a clinical measurement name to its standard adult reference interval
using a locally stored FHIR ObservationDefinition bundle keyed by LOINC codes.

Architecture
------------
1. A curated FHIR bundle (fhir_reference_ranges.json) stores ObservationDefinition
   resources exactly as a real FHIR server would serve them.
2. A name→LOINC mapping table (MEASUREMENT_NAME_MAP) translates the free-text
   measurement names extracted from PDFs into canonical LOINC codes.
3. For each LOINC code the engine reads qualifiedInterval entries and returns
   the most appropriate (low, high, unit) triple — optionally selecting a
   gender-specific interval if the caller supplies a gender hint.

This follows the LOINC+FHIR Option B design: same data model as a live FHIR
server, but hosted locally so it works offline and without auth.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("significance.loinc_range_lookup")

# ---------------------------------------------------------------------------
# Bundle path
# ---------------------------------------------------------------------------

_BUNDLE_FILE = Path(__file__).resolve().parent / "fhir_reference_ranges.json"

# ---------------------------------------------------------------------------
# Measurement name → LOINC code map
#
# Keys are lowercase, stripped strings (aliases) that may appear as measurement
# names in PDF extractions.  Values are LOINC codes matching entries in the
# FHIR bundle.  Multiple aliases can map to the same code.
# ---------------------------------------------------------------------------

MEASUREMENT_NAME_MAP: dict[str, str] = {
    # Blood pressure
    "systolic blood pressure": "8480-6",
    "systolic bp": "8480-6",
    "systolic": "8480-6",
    "sbp": "8480-6",
    "blood pressure systolic": "8480-6",

    "diastolic blood pressure": "8462-4",
    "diastolic bp": "8462-4",
    "diastolic": "8462-4",
    "dbp": "8462-4",
    "blood pressure diastolic": "8462-4",
    
    # Exclusions (to prevent generic word matching like 'systolic' matching PASP)
    "pulmonary artery systolic pressure": None,
    "pasp": None,
    "right ventricular systolic pressure": None,
    "rvsp": None,

    # Heart rate / pulse
    "heart rate": "8867-4",
    "pulse rate": "8867-4",
    "pulse": "8867-4",
    "hr": "8867-4",
    "pr": "8867-4",

    # BMI / weight / height
    "body mass index": "39156-5",
    "bmi": "39156-5",

    # Temperature
    "body temperature": "8310-5",
    "temperature": "8310-5",
    "temp": "8310-5",

    # CBC
    "hemoglobin": "718-7",
    "hgb": "718-7",
    "hb": "718-7",
    "haemoglobin": "718-7",

    "hematocrit": "4544-3",
    "hct": "4544-3",
    "packed cell volume": "4544-3",
    "pcv": "4544-3",

    "white blood cell count": "6690-2",
    "white blood cells": "6690-2",
    "wbc": "6690-2",
    "leukocyte count": "6690-2",
    "total leukocyte count": "6690-2",
    "tlc": "6690-2",

    "platelet count": "777-3",
    "platelets": "777-3",
    "plt": "777-3",

    # Glucose / HbA1c
    "fasting blood glucose": "1558-6",
    "fasting glucose": "1558-6",
    "fbg": "1558-6",
    "fbs": "1558-6",

    "blood glucose": "2345-7",
    "glucose": "2345-7",
    "random blood glucose": "2345-7",
    "rbs": "2345-7",
    "blood sugar": "2345-7",

    "hemoglobin a1c": "4548-4",
    "haemoglobin a1c": "4548-4",
    "hba1c": "4548-4",
    "glycated hemoglobin": "4548-4",
    "a1c": "4548-4",

    # Renal
    "creatinine": "2160-0",
    "serum creatinine": "2160-0",
    "cr": "2160-0",

    "blood urea nitrogen": "3094-0",
    "bun": "3094-0",
    "urea": "3094-0",
    "urea nitrogen": "3094-0",

    "uric acid": "3084-1",
    "serum uric acid": "3084-1",
    "urate": "3084-1",

    # Lipids
    "total cholesterol": "2093-3",
    "cholesterol": "2093-3",
    "tc": "2093-3",

    "ldl cholesterol": "13457-7",
    "ldl": "13457-7",
    "low density lipoprotein": "13457-7",

    "hdl cholesterol": "2085-9",
    "hdl": "2085-9",
    "high density lipoprotein": "2085-9",

    "triglycerides": "2571-8",
    "triglyceride": "2571-8",
    "tg": "2571-8",
    "vldl": "2571-8",

    # Liver
    "alanine aminotransferase": "1742-6",
    "alt": "1742-6",
    "sgpt": "1742-6",

    "aspartate aminotransferase": "1920-8",
    "ast": "1920-8",
    "sgot": "1920-8",

    "total bilirubin": "1975-2",
    "bilirubin": "1975-2",
    "tbil": "1975-2",

    "albumin": "1751-7",
    "serum albumin": "1751-7",

    # Thyroid
    "thyroid stimulating hormone": "3016-3",
    "tsh": "3016-3",
    "thyrotropin": "3016-3",

    # Electrolytes
    "sodium": "2951-2",
    "na": "2951-2",
    "serum sodium": "2951-2",

    "potassium": "2823-3",
    "k": "2823-3",
    "serum potassium": "2823-3",

    "chloride": "2075-0",
    "cl": "2075-0",
    "serum chloride": "2075-0",

    # Vitals
    "oxygen saturation": "59408-5",
    "spo2": "59408-5",
    "o2 saturation": "59408-5",
    "oxygen sat": "59408-5",

    "respiratory rate": "9279-1",
    "rr": "9279-1",
    "respiration rate": "9279-1",

    # Cardiac
    "ejection fraction": "8806-2",
    "lvef": "8806-2",
    "ef": "8806-2",
    "left ventricular ejection fraction": "8806-2",

    # Hormones (gynaecology/endocrine)
    "testosterone": "2986-8",
    "serum testosterone": "2986-8",

    "luteinizing hormone": "10501-5",
    "lh": "10501-5",

    "follicle stimulating hormone": "15067-2",
    "fsh": "15067-2",

    # Renal — eGFR (mapped to Creatinine-based eGFR LOINC)
    "egfr": "62238-1",
    "estimated gfr": "62238-1",
    "estimated glomerular filtration rate": "62238-1",
    "gfr": "62238-1",

    # Cholesterol ratios
    "ldl hdl ratio": "2089-1",
    "ldl/hdl": "2089-1",
    "cholesterol ldl": "2089-1",
    "ldl cholesterol": "2089-1",
    "ldl": "2089-1",
    "low density lipoprotein": "2089-1",
    "low-density lipoprotein": "2089-1",

    # Fasting insulin
    "insulin": "20448-7",
    "fasting insulin": "20448-7",
    "serum insulin": "20448-7",

    # HbA1c / Glycated haemoglobin
    "hba1c": "4548-4",
    "hemoglobin a1c": "4548-4",
    "haemoglobin a1c": "4548-4",
    "glycated hemoglobin": "4548-4",
    "glycosylated hemoglobin": "4548-4",
    "a1c": "4548-4",

    # DHEA-S (common in PCOS panels)
    "dhea-s": "2191-5",
    "dheas": "2191-5",
    "dehydroepiandrosterone sulfate": "2191-5",
    "dhea sulfate": "2191-5",
    
    # Ultrasound / Organ dimensions (Custom local codes)
    "right kidney": "C-KIDNEY-LEN",
    "left kidney": "C-KIDNEY-LEN",
    "kidney": "C-KIDNEY-LEN",
    "liver": "C-LIVER-LEN",
    "liver span": "C-LIVER-LEN",
    "spleen": "C-SPLEEN-LEN",
    "prostate volume": "C-PROSTATE",
    "prostate": "C-PROSTATE",
}


# ---------------------------------------------------------------------------
# Internal bundle loader (lazy-loaded singleton)
# ---------------------------------------------------------------------------

_BUNDLE_CACHE: Optional[dict[str, dict]] = None  # loinc_code → ObservationDefinition


def _load_bundle() -> dict[str, dict]:
    """
    Load the FHIR ObservationDefinition bundle from disk and index it by LOINC code.
    Result is cached in memory for the lifetime of the process.
    """
    global _BUNDLE_CACHE
    if _BUNDLE_CACHE is not None:
        return _BUNDLE_CACHE

    if not _BUNDLE_FILE.exists():
        logger.error("FHIR bundle not found: %s", _BUNDLE_FILE)
        _BUNDLE_CACHE = {}
        return _BUNDLE_CACHE

    try:
        with open(_BUNDLE_FILE, "r", encoding="utf-8") as f:
            bundle = json.load(f)
    except Exception as exc:
        logger.error("Failed to parse FHIR bundle: %s", exc)
        _BUNDLE_CACHE = {}
        return _BUNDLE_CACHE

    index: dict[str, dict] = {}
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") != "ObservationDefinition":
            continue
        for coding in resource.get("code", {}).get("coding", []):
            loinc_code = coding.get("code", "").strip()
            if loinc_code:
                index[loinc_code] = resource
                break  # first coding wins

    logger.info("FHIR bundle loaded: %d ObservationDefinition entries", len(index))
    _BUNDLE_CACHE = index
    return _BUNDLE_CACHE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_measurement_name(name: str) -> Optional[str]:
    """
    Resolve a free-text measurement name to a LOINC code.

    Matching is case-insensitive and strips leading/trailing whitespace.
    Returns the LOINC code string or None if no mapping exists.
    """
    if not name:
        return None
    clean = " ".join(name.strip().lower().split())
    loinc = MEASUREMENT_NAME_MAP.get(clean)
    if loinc:
        return loinc

    # Word-boundary matching — e.g. "serum alt" -> "alt"
    import re
    # Sort aliases by length descending so longer, more specific matches are tried first
    sorted_aliases = sorted(MEASUREMENT_NAME_MAP.items(), key=lambda x: len(x[0]), reverse=True)
    
    for alias, code in sorted_aliases:
        # Match if alias is a whole word inside the clean name
        # e.g., if alias="alt", matches "serum alt" or "alt level" but not "salt"
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, clean):
            return code

    return None


def get_fhir_reference_range(
    measurement_name: str,
    gender: Optional[str] = None,
) -> Optional[dict]:
    """
    Look up the standard FHIR-structured reference range for a measurement.

    Parameters
    ----------
    measurement_name:
        Free-text name of the measurement as it appears in the extracted report.
    gender:
        Optional gender hint for gender-specific ranges. Accepts 'male', 'female'
        (case-insensitive). When None, the first available interval is returned.

    Returns
    -------
    dict or None
        A dict with keys ``low``, ``high``, ``unit``, ``loinc_code``,
        ``display_name``, and ``source`` if a range is found, otherwise None.

        Example::

            {
                "low": 90.0,
                "high": 120.0,
                "unit": "mmHg",
                "loinc_code": "8480-6",
                "display_name": "Systolic blood pressure",
                "source": "LOINC+FHIR R4"
            }
    """
    loinc_code = resolve_measurement_name(measurement_name)
    if not loinc_code:
        logger.debug("No LOINC code mapping for: %r", measurement_name)
        return None

    bundle = _load_bundle()
    obs_def = bundle.get(loinc_code)
    if not obs_def:
        logger.debug("LOINC code %r not in bundle", loinc_code)
        return None

    display_name = (
        obs_def.get("preferredReportName")
        or obs_def.get("code", {}).get("coding", [{}])[0].get("display", measurement_name)
    )

    intervals: list[dict] = obs_def.get("qualifiedInterval", [])
    if not intervals:
        return None

    # Normalise gender hint
    gender_hint = (gender or "").strip().lower()
    if gender_hint not in ("male", "female"):
        gender_hint = None

    # Select the best interval:
    #   1. Exact gender match (if hint supplied)
    #   2. No gender field (universal)
    #   3. Any interval as last resort
    selected = None

    for interval in intervals:
        cat = interval.get("category", "reference")
        if cat not in ("reference", "normal"):
            continue  # skip critical/absolute ranges

        interval_gender = interval.get("gender", "").lower()

        if gender_hint and interval_gender == gender_hint:
            selected = interval
            break
        if not interval_gender and selected is None:
            selected = interval  # universal range — prefer over nothing

    if selected is None and intervals:
        selected = intervals[0]  # last resort

    if selected is None:
        return None

    low_q = selected.get("range", {}).get("low", {})
    high_q = selected.get("range", {}).get("high", {})

    try:
        low_val = float(low_q.get("value", ""))
        high_val = float(high_q.get("value", ""))
    except (TypeError, ValueError):
        logger.debug("Malformed range bounds in FHIR bundle for LOINC %r", loinc_code)
        return None

    unit = (
        low_q.get("unit")
        or high_q.get("unit")
        or obs_def.get("quantitativeDetails", {})
        .get("unit", {})
        .get("coding", [{}])[0]
        .get("display", "")
    )

    return {
        "low": low_val,
        "high": high_val,
        "unit": unit,
        "loinc_code": loinc_code,
        "display_name": display_name,
        "source": "LOINC+FHIR R4",
    }


# ---------------------------------------------------------------------------
# Blood pressure compound value helpers
# ---------------------------------------------------------------------------

# Matches "118/76", "120 / 80", "118/76 mmHg"
_COMPOUND_BP_RE = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*/\s*([+-]?\d+(?:\.\d+)?)"
)

_BP_CONCEPT_PATTERNS = (
    "blood pressure",
    "bp",
    "arterial pressure",
)


def parse_blood_pressure(value_str: str) -> Optional[tuple]:
    """
    Parse a compound blood pressure string like '118/76' or '120/80 mmHg'.

    Returns (systolic: float, diastolic: float) or None if not compound format.
    """
    if not value_str:
        return None
    m = _COMPOUND_BP_RE.match(str(value_str).strip())
    if not m:
        return None
    try:
        return float(m.group(1)), float(m.group(2))
    except (TypeError, ValueError):
        return None


def is_blood_pressure_concept(name: str) -> bool:
    """Return True if *name* refers to a blood pressure measurement."""
    clean = name.strip().lower()
    return any(pat in clean for pat in _BP_CONCEPT_PATTERNS)


def get_bp_fhir_ranges() -> tuple:
    """
    Return (systolic_range_dict, diastolic_range_dict) from the FHIR bundle.
    Either element may be None if not found.
    """
    systolic = get_fhir_reference_range("systolic blood pressure")
    diastolic = get_fhir_reference_range("diastolic blood pressure")
    return systolic, diastolic


def get_patient_gender(report_json: dict) -> str | None:
    """
    Extract patient gender from a normalized report JSON dict.

    Searches, in order:
      1. report_json["patient_info"]["gender"]
      2. report_json["metadata"]["patient_gender"]
      3. Keywords in clinical section text ("female", "male", "woman", "man", "f/", "m/")

    Returns 'male', 'female', or None.
    """
    if not report_json:
        return None

    # 1. Structured patient info
    for path in (
        ("patient_info", "gender"),
        ("patient_info", "sex"),
        ("metadata", "patient_gender"),
        ("metadata", "sex"),
        ("header", "gender"),
    ):
        val = report_json
        for key in path:
            if not isinstance(val, dict):
                break
            val = val.get(key)
        if isinstance(val, str) and val.strip():
            clean = val.strip().lower()
            if clean in ("female", "f", "woman", "girl"):
                return "female"
            if clean in ("male", "m", "man", "boy"):
                return "male"

    # 2. Keyword scan in section text (e.g. "Age: 28 years, Female")
    import re as _re
    _FEMALE_RE = _re.compile(
        r"\b(female|woman|girl|f(?:emale)?)\b", _re.IGNORECASE
    )
    _MALE_RE = _re.compile(
        r"\b(male|man|boy|m(?:ale)?)\b", _re.IGNORECASE
    )
    # Scan metadata string fields
    for section in (
        report_json.get("raw_text_preview", ""),
        str(report_json.get("patient_info", "")),
        str(report_json.get("metadata", "")),
    ):
        text = str(section)
        if _FEMALE_RE.search(text):
            return "female"
        if _MALE_RE.search(text):
            return "male"

    return None
