"""
Deterministic reference range comparison engine for ClinRESET.
Evaluates numeric measurements strictly against in-situ or reported reference intervals.
Never invents, infers, or guesses unstated clinical bounds.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Tuple

from .models import ComparisonResult

logger = logging.getLogger(__name__)

# Regex pattern for numeric intervals with optional units: e.g. '06-11mm', '20-37 mm', '55-74%', '12 - 16 g/dL'
RANGE_PATTERN = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*(?:-|to)\s*([+-]?\d+(?:\.\d+)?)\s*([a-zA-Z/%°\^].*)?$",
    re.IGNORECASE,
)


def parse_numeric_value(val: Any) -> Optional[float]:
    """Parses int, float, or numeric string into a float. Returns None on failure."""
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
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Extracts inclusive (low, high, unit) bounds from a reference range representation.
    Supports strings ('06-11mm', '55-74%'), dicts ({'low': ..., 'high': ...}), or objects.
    """
    if reference_range is None:
        return None, None, None

    # 1. Dict format
    if isinstance(reference_range, dict):
        if "low" not in reference_range or "high" not in reference_range:
            return None, None, None
        low = parse_numeric_value(reference_range.get("low"))
        high = parse_numeric_value(reference_range.get("high"))
        unit = reference_range.get("unit")
        return low, high, str(unit).strip() if unit else None

    # 2. Object with attributes
    if hasattr(reference_range, "low") and hasattr(reference_range, "high"):
        low = parse_numeric_value(getattr(reference_range, "low"))
        high = parse_numeric_value(getattr(reference_range, "high"))
        unit = getattr(reference_range, "unit", None)
        return low, high, str(unit).strip() if unit else None

    # 3. String format: '06-11mm', '6 to 11 mm', '55-74%'
    if isinstance(reference_range, str):
        s = reference_range.strip()
        if not s:
            return None, None, None

        # Strip surrounding parentheses e.g. '(06-11mm)'
        s = re.sub(r"^\(|\)$", "", s).strip()

        match = RANGE_PATTERN.match(s)
        if match:
            low = parse_numeric_value(match.group(1))
            high = parse_numeric_value(match.group(2))
            unit_str = match.group(3).strip() if match.group(3) else None
            return low, high, unit_str

    return None, None, None


def compare_to_range(
    value: Any,
    reference_range: Any,
) -> ComparisonResult:
    """
    Deterministically evaluates a measured numeric value against a reported reference interval.
    Inclusive comparisons: low <= value <= high -> WITHIN_REPORTED_RANGE.
    """
    num = parse_numeric_value(value)
    if num is None:
        return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED

    low, high, _ = parse_reference_bounds(reference_range)
    if low is None or high is None:
        return ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED

    if num < low:
        return ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
    elif num > high:
        return ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
    else:
        return ComparisonResult.WITHIN_REPORTED_RANGE
