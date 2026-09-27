"""
significance/range_engine.py

Pure functional engine for evaluating numeric measurements against reported reference intervals.

Strictly preserves reported intervals without inventing or inferring unstated bounds.
Handles inclusive comparisons, multiple numeric representations (int, float, numeric strings),
and gracefully handles malformed or missing ranges.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from significance.models import ComparisonResult

logger = logging.getLogger("significance.range_engine")

# Regex to extract low and high numeric bounds with optional trailing unit from strings
# Examples: '06-11mm', '20-37mm', '55-74%', '12 - 16 g/dL', '3.5 - 5.0'
RANGE_STRING_PATTERN = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*-\s*([+-]?\d+(?:\.\d+)?)\s*([a-zA-Z/%°\^].*)?$",
    re.IGNORECASE,
)


def parse_numeric_value(val: Any) -> Optional[float]:
    """
    Parse an int, float, or numeric string into a float.

    Returns None if the value cannot be interpreted as a valid finite number.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.strip().rstrip("%").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def parse_reference_bounds(
    reference_range: Any,
) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Extract inclusive (low, high, unit) bounds from a reference range representation.

    Supports:
    1. Dicts with 'low' and 'high' keys (and optional 'unit')
    2. Objects with 'low' and 'high' attributes
    3. Strings in 'low - high [unit]' format (e.g., '06-11mm', '55-74%')

    Returns
    -------
    tuple[Optional[float], Optional[float], Optional[str]]
        (low, high, unit) if valid numeric bounds are present, else (None, None, None).
    """
    if reference_range is None:
        return None, None, None

    # 1. Dict format: {'low': ..., 'high': ...}
    if isinstance(reference_range, dict):
        if "low" not in reference_range or "high" not in reference_range:
            return None, None, None
        low = parse_numeric_value(reference_range.get("low"))
        high = parse_numeric_value(reference_range.get("high"))
        unit = reference_range.get("unit")
        unit_str = str(unit).strip() if unit is not None else None
        return low, high, unit_str

    # 2. Object with attributes
    if hasattr(reference_range, "low") and hasattr(reference_range, "high"):
        low = parse_numeric_value(getattr(reference_range, "low"))
        high = parse_numeric_value(getattr(reference_range, "high"))
        unit = getattr(reference_range, "unit", None)
        unit_str = str(unit).strip() if unit is not None else None
        return low, high, unit_str

    # 3. String format: e.g. '06-11mm', '20-37 mm', '55-74%'
    if isinstance(reference_range, str):
        ref_str = reference_range.strip()
        if not ref_str:
            return None, None, None
        match = RANGE_STRING_PATTERN.match(ref_str)
        if match:
            low = parse_numeric_value(match.group(1))
            high = parse_numeric_value(match.group(2))
            unit_str = match.group(3).strip() if match.group(3) else None
            return low, high, unit_str
        return None, None, None

    return None, None, None


def compare_to_range(value: Any, reference_range: Any) -> ComparisonResult:
    """
    Compare a numeric measurement against a reported reference interval.

    Parameters
    ----------
    value:
        Numeric measurement (int, float, or numeric string).
    reference_range:
        Reported reference interval (dict with 'low'/'high' keys, or string like '06-11mm').

    Returns
    -------
    ComparisonResult:
        WITHIN_REPORTED_RANGE, ABOVE_REPORTED_REFERENCE_RANGE,
        BELOW_REPORTED_REFERENCE_RANGE, or NO_REFERENCE_RANGE_SUPPLIED.
    """
    if reference_range is None:
        return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED

    if value is None:
        return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED

    num_val = parse_numeric_value(value)
    if num_val is None:
        logger.warning(
            "Malformed or non-numeric measurement value passed to compare_to_range: %r",
            value,
        )
        return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED

    # Check dict structure if passed as dict
    if isinstance(reference_range, dict):
        if "low" not in reference_range or "high" not in reference_range:
            return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
        raw_low = reference_range.get("low")
        raw_high = reference_range.get("high")
        low = parse_numeric_value(raw_low)
        high = parse_numeric_value(raw_high)
        if low is None or high is None:
            logger.warning(
                "Malformed non-numeric bounds in reference_range dict: low=%r, high=%r",
                raw_low,
                raw_high,
            )
            return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
    elif isinstance(reference_range, str):
        low, high, _ = parse_reference_bounds(reference_range)
        if low is None or high is None:
            logger.warning(
                "Malformed or unparseable reference_range string passed to compare_to_range: %r",
                reference_range,
            )
            return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
    else:
        low, high, _ = parse_reference_bounds(reference_range)
        if low is None or high is None:
            logger.warning(
                "Unsupported reference_range format or missing bounds: %r",
                reference_range,
            )
            return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED

    # Inclusive comparison
    if num_val < low:
        return ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
    if num_val > high:
        return ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
    return ComparisonResult.WITHIN_REPORTED_RANGE
