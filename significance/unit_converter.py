"""
significance/unit_converter.py

Unit normalization and conversion for clinical measurements.

Handles the case where an extracted measurement value is in a different unit
than the LOINC FHIR reference range (e.g. temperature in °F vs °C,
or "bpm" vs "/min").

Design
------
1. UNIT_ALIASES  — maps raw unit strings to canonical UCUM codes.
2. CONVERTIBLE   — defines conversion functions between pairs of units.
3. normalize_unit(raw)   — canonicalize a raw unit string.
4. convert_value(value, from_unit, to_unit) — apply the conversion formula.
5. prepare_for_comparison(value, value_unit, range_unit)
       — returns (converted_value, effective_unit) ready for numeric comparison.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("significance.unit_converter")

# ---------------------------------------------------------------------------
# Unit alias map — raw string → canonical UCUM code
# ---------------------------------------------------------------------------
# Add new aliases here; keys are lowercase stripped.

UNIT_ALIASES: dict[str, str] = {
    # Temperature
    "°c": "Cel",
    "c": "Cel",
    "celsius": "Cel",
    "degc": "Cel",
    "deg c": "Cel",
    "degree c": "Cel",
    "degrees c": "Cel",
    "degrees celsius": "Cel",
    "cel": "Cel",
    "°f": "[degF]",
    "f": "[degF]",
    "fahrenheit": "[degF]",
    "degf": "[degF]",
    "deg f": "[degF]",
    "degree f": "[degF]",
    "degree_f": "[degF]",
    "degrees f": "[degF]",
    "degrees fahrenheit": "[degF]",
    "[degf]": "[degF]",

    # Pressure
    "mmhg": "mm[Hg]",
    "mm hg": "mm[Hg]",
    "mm[hg]": "mm[Hg]",
    "torr": "mm[Hg]",

    # Heart / respiratory rate
    "bpm": "/min",
    "beats/min": "/min",
    "beats per minute": "/min",
    "breaths/min": "/min",
    "breaths per minute": "/min",
    "/min": "/min",

    # Mass/volume
    "g/dl": "g/dL",
    "g/dL": "g/dL",
    "mg/dl": "mg/dL",
    "mg/dL": "mg/dL",
    "µg/dl": "ug/dL",
    "ug/dl": "ug/dL",
    "ng/dl": "ng/dL",
    "ng/ml": "ng/mL",
    "pg/ml": "pg/mL",
    "iu/l": "IU/L",
    "iu/ml": "IU/mL",
    "miu/l": "mIU/L",
    "miu/ml": "mIU/mL",
    "u/l": "U/L",
    "u/ml": "U/mL",

    # Moles/volume
    "mmol/l": "mmol/L",
    "umol/l": "umol/L",
    "nmol/l": "nmol/L",

    # Ratios / fractions
    "%": "%",
    "percent": "%",

    # BMI
    "kg/m2": "kg/m2",
    "kg/m²": "kg/m2",

    # Cell counts
    "10*3/ul": "10*3/uL",
    "10^3/ul": "10*3/uL",
    "k/ul": "10*3/uL",
    "cells/ul": "10*3/uL",
    "10*3/µl": "10*3/uL",

    # Oxygen saturation
    "spo2": "%",
    "sat": "%",
}


# ---------------------------------------------------------------------------
# Conversion function registry
# keys are (from_canonical, to_canonical) tuples
# ---------------------------------------------------------------------------

def _c_to_f(v: float) -> float:
    return (v * 9 / 5) + 32

def _f_to_c(v: float) -> float:
    return (v - 32) * 5 / 9

def _mgdl_to_mmoll_glucose(v: float) -> float:
    return v / 18.0

def _mmoll_to_mgdl_glucose(v: float) -> float:
    return v * 18.0

def _gdl_to_gL(v: float) -> float:
    return v * 10.0

def _gL_to_gdl(v: float) -> float:
    return v / 10.0


CONVERTERS: dict[tuple[str, str], callable] = {
    # Temperature
    ("Cel", "[degF]"): _c_to_f,
    ("[degF]", "Cel"): _f_to_c,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_unit(raw: Optional[str]) -> Optional[str]:
    """
    Return the canonical UCUM code for a raw unit string.

    Returns the original string unchanged if no alias matches,
    so it is always safe to call even on unknown units.
    """
    if not raw:
        return raw
    key = raw.strip().lower()
    return UNIT_ALIASES.get(key, UNIT_ALIASES.get(raw.strip(), raw.strip()))


def convert_value(
    value: float,
    from_unit: Optional[str],
    to_unit: Optional[str],
) -> Optional[float]:
    """
    Convert *value* from *from_unit* to *to_unit*.

    Returns the converted value, or None if no conversion is registered.
    Both units are first normalised via normalize_unit().
    """
    if from_unit is None or to_unit is None:
        return None
    f = normalize_unit(from_unit)
    t = normalize_unit(to_unit)
    if f == t:
        return value
    fn = CONVERTERS.get((f, t))
    if fn is None:
        logger.debug("No converter for %r → %r", f, t)
        return None
    result = fn(value)
    logger.info(
        "Unit conversion: %.4f %s → %.4f %s", value, f, result, t
    )
    return result


def prepare_for_comparison(
    value: float,
    value_unit: Optional[str],
    range_unit: Optional[str],
) -> tuple[Optional[float], str]:
    """
    Convert *value* (in *value_unit*) to *range_unit* if possible,
    so both sides of the comparison are in the same unit.

    Returns (effective_value, effective_unit):
      - If conversion succeeds → (converted_value, range_unit)
      - If same unit → (value, range_unit or value_unit)
      - If no conversion available → (value, value_unit or range_unit)
    """
    v_canon = normalize_unit(value_unit)
    r_canon = normalize_unit(range_unit)

    if v_canon and r_canon and v_canon != r_canon:
        converted = convert_value(value, v_canon, r_canon)
        if converted is not None:
            return converted, r_canon or range_unit or ""
        else:
            # Units exist, are different, and cannot be converted.
            # Reject the comparison entirely.
            return None, v_canon or value_unit or ""

    # Either same unit, or one is missing (assume they match). Prefer extracted unit.
    return value, v_canon or value_unit or r_canon or range_unit or ""
