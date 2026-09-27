"""
clinical_extraction/measurements.py

Structured measurement extraction and ingestion.

Reuses the normalized measurements produced by Phase 1 and extracts any
inline measurements present in section text narratives (e.g., 'PASP=34mmHg').
"""

from __future__ import annotations

import re
from typing import Any, Optional

from clinical_extraction.models import ClinicalMeasurement
from clinical_extraction.normalization import normalize_term


# Regex to detect inline measurements like:
# PASP=34mmHg, PASP = 34 mmHg, Aortic Velocity = 1.47 m/s, EF: 60%
INLINE_MEASUREMENT_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z0-9\s\.\-_/]{1,30}?)\s*[:=]\s*([<>]?\s*\d+(?:\.\d+)?)\s*([a-zA-Z/%°][a-zA-Z0-9/%°\^]*)?\b",
    re.IGNORECASE,
)


def _parse_value(raw_val: Any) -> Any:
    """Parse numeric string to int or float if possible, otherwise retain string."""
    if raw_val is None:
        return None
    val_str = str(raw_val).strip()
    # Strip any trailing % if value itself has it
    if val_str.endswith("%"):
        val_str = val_str[:-1].strip()

    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        return str(raw_val).strip()


def _clean_ref_range(ref: Optional[str]) -> Optional[str]:
    """Clean reference range string or return None if empty/absent."""
    if not ref:
        return None
    cleaned = ref.strip("() \t\r\n")
    if not cleaned or cleaned.upper() == "NORMAL VALUES" or cleaned.upper() == "NORMAL":
        return None
    return cleaned


def extract_measurements(
    phase1_measurements: list[Any],
    sections: list[Any],
    report_type: Optional[str] = None,
) -> list[ClinicalMeasurement]:
    """
    Extract all clinical measurements by reusing Phase 1 measurements and
    detecting any inline narrative measurements.

    Parameters
    ----------
    phase1_measurements:
        List of extraction.models.Measurement objects from Phase 1.
    sections:
        List of extraction.models.Section objects to scan for inline measurements.
    report_type:
        Identified report type for normalization context.

    Returns
    -------
    list[ClinicalMeasurement]
        Consolidated list of structured clinical measurements.
    """
    measurements: list[ClinicalMeasurement] = []
    seen_keys: set[tuple[str, Any]] = set()

    # 1. Ingest existing Phase 1 measurements
    for m in phase1_measurements:
        if not m.name or m.value is None:
            continue

        parsed_val = _parse_value(m.value)
        unit = m.unit.strip() if m.unit else None
        ref_range = _clean_ref_range(m.reference_range)

        # Do not invent unit or ref range
        norm_name = normalize_term(m.name, report_type)

        meas = ClinicalMeasurement(
            name=m.name.strip(),
            value=parsed_val,
            unit=unit,
            reference_range=ref_range,
            page=m.page,
            source_section=m.source_section,
            source_text=f"{m.name}: {m.value}{(' ' + unit) if unit else ''}",
            normalized_name=norm_name,
        )
        measurements.append(meas)
        seen_keys.add((m.name.strip().lower(), str(parsed_val)))

    # 2. Extract inline narrative measurements from section text
    for sec in sections:
        sec_text = getattr(sec, "text", "") or ""
        sec_title = getattr(sec, "title", None)
        sec_page = getattr(sec, "page", None)

        if not sec_text:
            continue

        # Look for inline measurements in lines
        for line in sec_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            for match in INLINE_MEASUREMENT_PATTERN.finditer(line_str):
                raw_param_name = match.group(1).strip(" -*#_<>")
                param_val_str = match.group(2).strip()
                raw_unit = match.group(3).strip(" .") if match.group(3) else None

                # Clean parameter name from preceding words if it ends with known parameter
                param_name = raw_param_name
                # If name ends with PASP, EF, etc., isolate it
                for known_param in ("PASP", "EF", "FS", "LVEDD", "LVESD", "IVSd", "LVPWd"):
                    if re.search(rf"\b{known_param}\b", param_name, re.IGNORECASE):
                        param_name = known_param
                        break

                # Strip leading single letter artifacts like "A Aortic Velocity" -> "Aortic Velocity"
                if re.match(r"^[A-Za-z]\s+[A-Za-z]", param_name):
                    param_name = re.sub(r"^[A-Za-z]\s+", "", param_name)

                # Filter out obvious false positives like "DATED: AGE", "AGE/SEX", "PAGE: 1"
                excluded_params = {
                    "dated", "ref by", "age", "sex", "age/sex",
                    "page", "id", "name", "dr", "no", "date", "ipd", "opd",
                }
                if param_name.lower() in excluded_params:
                    continue

                parsed_val = _parse_value(param_val_str)
                key = (param_name.lower(), str(parsed_val))
                if key in seen_keys:
                    continue

                norm_name = normalize_term(param_name, report_type)

                inline_meas = ClinicalMeasurement(
                    name=param_name,
                    value=parsed_val,
                    unit=raw_unit,
                    reference_range=None,
                    page=sec_page,
                    source_section=sec_title,
                    source_text=line_str,
                    normalized_name=norm_name,
                )
                measurements.append(inline_meas)
                seen_keys.add(key)

    return measurements
