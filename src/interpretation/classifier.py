"""
Clinical concept significance and alert classifier for ClinRESET.
Evaluates clinical findings and measurements against reported ranges and assertions.
Assigns factual triage alert indicators (GREEN, YELLOW, ORANGE, RED, GREY).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .models import AlertLevel, ComparisonResult, SignificanceLevel, SignificanceResult
from .range_engine import compare_to_range, parse_numeric_value, parse_reference_bounds

logger = logging.getLogger(__name__)

# Static mapping from significance level to triage alert level
SIGNIFICANCE_ALERT_MAP: Dict[SignificanceLevel, AlertLevel] = {
    SignificanceLevel.INFORMATIONAL: AlertLevel.GREEN,
    SignificanceLevel.WITHIN_REPORTED_RANGE: AlertLevel.GREEN,
    SignificanceLevel.NOTABLE_FINDING: AlertLevel.YELLOW,
    SignificanceLevel.OUTSIDE_REPORTED_RANGE: AlertLevel.ORANGE,
    SignificanceLevel.REQUIRES_CONTEXT: AlertLevel.GREY,
    SignificanceLevel.UNRESOLVED: AlertLevel.GREY,
    SignificanceLevel.CRITICAL: AlertLevel.RED,
}

# Critical finding triggers requiring urgent alert (life-threatening findings)
CRITICAL_TRIGGERS = [
    "tension pneumothorax",
    "cardiac tamponade",
    "aortic dissection",
    "massive pulmonary embolism",
    "acute myocardial infarction",
]


class ConceptClassifier:
    """Deterministically classifies finding significance and alert levels."""

    @classmethod
    def classify(
        cls,
        concept: str,
        assertion: str = "PRESENT",
        value: Optional[Any] = None,
        unit: Optional[str] = None,
        reference_range: Optional[Any] = None,
        source_text: Optional[str] = None,
    ) -> SignificanceResult:
        """
        Classifies clinical significance and assigns triage indicator.
        """
        concept_clean = concept.strip() if concept else "Unknown Finding"
        assertion_norm = assertion.upper().strip()
        num_val = parse_numeric_value(value)

        # -------------------------------------------------------------------
        # Case 1: Quantitative Concept (has numeric measurement)
        # -------------------------------------------------------------------
        if num_val is not None:
            comparison = compare_to_range(num_val, reference_range)
            low, high, ref_unit = parse_reference_bounds(reference_range)
            effective_unit = unit or ref_unit or ""

            if comparison == ComparisonResult.WITHIN_REPORTED_RANGE:
                significance = SignificanceLevel.WITHIN_REPORTED_RANGE
                basis = (
                    f"Measured value of {num_val}{' ' + effective_unit if effective_unit else ''} "
                    f"falls within reported reference range ({low}-{high}{effective_unit})."
                )
            elif comparison in (ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE, ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE):
                significance = SignificanceLevel.OUTSIDE_REPORTED_RANGE
                direction = "above" if comparison == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE else "below"
                basis = (
                    f"Measured value of {num_val}{' ' + effective_unit if effective_unit else ''} "
                    f"is {direction} reported reference range ({low}-{high}{effective_unit})."
                )
            else:
                significance = SignificanceLevel.REQUIRES_CONTEXT
                basis = (
                    f"Measurement reported as {num_val}{' ' + effective_unit if effective_unit else ''} "
                    "without an in-situ reference interval; clinical significance depends on overall context."
                )

            alert = SIGNIFICANCE_ALERT_MAP.get(significance, AlertLevel.GREY)
            ref_str = f"{low}-{high} {effective_unit}".strip() if low is not None and high is not None else None

            return SignificanceResult(
                concept=concept_clean,
                comparison=comparison,
                significance=significance,
                alert_level=alert,
                basis=basis,
                value=num_val,
                unit=effective_unit or None,
                reference_range=ref_str,
            )

        # -------------------------------------------------------------------
        # Case 2: Qualitative Finding (no numeric measurement)
        # -------------------------------------------------------------------
        comparison = ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED

        if assertion_norm in ("NORMAL", "ABSENT"):
            significance = SignificanceLevel.INFORMATIONAL
            alert = AlertLevel.GREEN
            if assertion_norm == "NORMAL":
                basis = f"Report explicitly characterizes '{concept_clean}' as normal or within expected limits."
            else:
                basis = f"Report explicitly documents the absence or negative finding of '{concept_clean}'."

        elif assertion_norm == "PRESENT":
            # Check for critical life-threatening conditions
            c_lower = concept_clean.lower()
            text_lower = (source_text or "").lower()
            if any(t in c_lower or t in text_lower for t in CRITICAL_TRIGGERS):
                significance = SignificanceLevel.CRITICAL
                alert = AlertLevel.RED
                basis = f"Documented finding of '{concept_clean}' represents an acute emergency condition requiring urgent clinical attention."
            else:
                significance = SignificanceLevel.NOTABLE_FINDING
                alert = AlertLevel.YELLOW
                basis = f"Finding '{concept_clean}' is documented as PRESENT, representing a notable clinical observation."

        else:  # POSSIBLE or UNKNOWN
            significance = SignificanceLevel.UNRESOLVED
            alert = AlertLevel.GREY
            basis = f"Finding '{concept_clean}' has indeterminate or uncertain assertion status ({assertion_norm})."

        return SignificanceResult(
            concept=concept_clean,
            comparison=comparison,
            significance=significance,
            alert_level=alert,
            basis=basis,
            value=None,
            unit=unit,
            reference_range=None,
        )
