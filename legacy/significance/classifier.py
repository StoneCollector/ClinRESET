"""
significance/classifier.py

Clinical concept significance classification engine.

Evaluates structured clinical concept dictionaries (from report.json) against
reported reference intervals and assertion states. Strictly avoids clinical
speculation or unverified severity claims.
"""

from __future__ import annotations

import logging
from typing import Any

from significance.alerts import map_to_alert
from significance.models import (
    AlertLevel,
    ComparisonResult,
    SignificanceLevel,
    SignificanceResult,
)
from significance.range_engine import (
    compare_to_range,
    parse_numeric_value,
    parse_reference_bounds,
)

logger = logging.getLogger("significance.classifier")

# ---------------------------------------------------------------------------
# Module-level configuration and mappings
# ---------------------------------------------------------------------------

# Mapping from qualitative finding assertion to significance level
ASSERTION_SIGNIFICANCE_MAP: dict[str, SignificanceLevel] = {
    "NORMAL": SignificanceLevel.INFORMATIONAL,
    "ABSENT": SignificanceLevel.INFORMATIONAL,
    "PRESENT": SignificanceLevel.NOTABLE_FINDING,
    "POSSIBLE": SignificanceLevel.UNRESOLVED,
    "UNKNOWN": SignificanceLevel.UNRESOLVED,
}

# Mapping from quantitative comparison result to significance level
COMPARISON_SIGNIFICANCE_MAP: dict[ComparisonResult, SignificanceLevel] = {
    ComparisonResult.WITHIN_REPORTED_RANGE: SignificanceLevel.WITHIN_REPORTED_RANGE,
    ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE: SignificanceLevel.OUTSIDE_REPORTED_RANGE,
    ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE: SignificanceLevel.OUTSIDE_REPORTED_RANGE,
    ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED: SignificanceLevel.REQUIRES_CONTEXT,
}

# TODO: In future iterations, domain experts can register validated rules mapping
# specific high-urgency conditions (e.g. cardiac tamponade, aortic dissection)
# to SignificanceLevel.CRITICAL. For this first deterministic pass, CRITICAL is
# NEVER automatically assigned.
CRITICAL_OVERRIDES: dict[str, Any] = {}


def _format_bound_num(num: float) -> str:
    """Format a float cleanly without trailing .0 if integer."""
    return f"{int(num)}" if num.is_integer() else f"{num}"


def classify_concept(concept: dict[str, Any]) -> SignificanceResult:
    """
    Classify the clinical significance and alert level of a single structured clinical concept.

    Parameters
    ----------
    concept:
        A structured clinical concept dictionary matching the schema from report.json
        (with keys: concept, original_text, type, value, unit, reference_range, assertion, modifiers).

    Returns
    -------
    SignificanceResult:
        Evaluated significance result with concept name, comparison, significance, alert_level, and basis.
    """
    concept_name = concept.get("concept") or concept.get("original_text") or "Unknown Concept"
    raw_val = concept.get("value")
    ref_range = concept.get("reference_range")
    unit = concept.get("unit")
    assertion = str(concept.get("assertion", "PRESENT")).upper()
    modifiers = concept.get("modifiers") or {}

    num_val = parse_numeric_value(raw_val)

    # -----------------------------------------------------------------------
    # Case 1: Quantitative Concept (has numeric value)
    # -----------------------------------------------------------------------
    if num_val is not None:
        comparison = compare_to_range(num_val, ref_range)
        significance = COMPARISON_SIGNIFICANCE_MAP.get(
            comparison, SignificanceLevel.REQUIRES_CONTEXT
        )

        low, high, ref_unit = parse_reference_bounds(ref_range)
        effective_unit = unit or ref_unit or ""

        # Format clean value string
        val_display = _format_bound_num(num_val)
        if effective_unit == "%":
            val_str = f"{val_display} %"
        elif effective_unit:
            val_str = f"{val_display} {effective_unit}"
        else:
            val_str = f"{val_display}"

        # Construct factual basis
        if comparison == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED or low is None or high is None:
            basis = f"Value {val_str} is reported without a reference range"
        else:
            low_str = _format_bound_num(low)
            high_str = _format_bound_num(high)
            if effective_unit == "%":
                range_str = f"{low_str}-{high_str} %"
            elif effective_unit:
                range_str = f"{low_str}-{high_str} {effective_unit}"
            else:
                range_str = f"{low_str}-{high_str}"

            if comparison == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE:
                basis = f"Value {val_str} is above the reported reference range {range_str}"
            elif comparison == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE:
                basis = f"Value {val_str} is below the reported reference range {range_str}"
            else:
                basis = f"Value {val_str} is within the reported reference range {range_str}"

    # -----------------------------------------------------------------------
    # Case 2: Qualitative Concept (no numeric value)
    # -----------------------------------------------------------------------
    else:
        comparison = ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
        significance = ASSERTION_SIGNIFICANCE_MAP.get(
            assertion, SignificanceLevel.UNRESOLVED
        )

        # Build informative factual basis based on assertion
        if assertion == "NORMAL":
            basis = "Finding reported as normal"
        elif assertion == "ABSENT":
            basis = "Finding reported as absent"
        elif assertion == "PRESENT":
            mod_items = [str(v) for v in modifiers.values() if v]
            if mod_items:
                mod_desc = ", ".join(mod_items)
                basis = f"Finding reported as present ({mod_desc})"
            else:
                basis = "Finding reported as present"
        elif assertion in ("POSSIBLE", "UNKNOWN"):
            basis = f"Finding reported with {assertion.lower()} assertion"
        else:
            basis = f"Finding evaluated with assertion: {assertion}"

    # -----------------------------------------------------------------------
    # Critical overrides check (always disabled in initial pass)
    # -----------------------------------------------------------------------
    # Ensure CRITICAL is never auto-assigned in this initial pass
    if concept_name in CRITICAL_OVERRIDES:
        # Placeholder for future human-validated overrides
        pass

    alert_level = map_to_alert(significance)

    return SignificanceResult(
        concept=concept_name,
        comparison=comparison,
        significance=significance,
        alert_level=alert_level,
        basis=basis,
    )
