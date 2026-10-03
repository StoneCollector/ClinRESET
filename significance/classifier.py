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
from significance.loinc_range_lookup import (
    get_bp_fhir_ranges,
    get_fhir_reference_range,
    is_blood_pressure_concept,
    parse_blood_pressure,
)
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
from significance.unit_converter import normalize_unit, prepare_for_comparison

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
    """Format a float cleanly: strip trailing .0 for integers, cap at 2dp."""
    rounded = round(num, 2)
    return f"{int(rounded)}" if rounded == int(rounded) else f"{rounded}"


def classify_concept(
    concept: dict[str, Any],
    patient_context: dict[str, Any] | None = None,
) -> SignificanceResult:
    """
    Classify the clinical significance and alert level of a single structured clinical concept.

    Parameters
    ----------
    concept:
        A structured clinical concept dictionary matching the schema from report.json
        (with keys: concept, original_text, type, value, unit, reference_range, assertion, modifiers).
    patient_context:
        Optional report-level context dict. Currently supports ``{"gender": "male"|"female"}``
        for gender-aware reference range selection.

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
    gender = (patient_context or {}).get("gender")

    num_val = parse_numeric_value(raw_val)

    # -----------------------------------------------------------------------
    # Special Case: Compound blood pressure value (e.g. '118/76')
    # Evaluate systolic and diastolic components separately.
    # -----------------------------------------------------------------------
    if num_val is None and is_blood_pressure_concept(concept_name):
        bp = parse_blood_pressure(str(raw_val) if raw_val is not None else "")
        if bp:
            systolic, diastolic = bp
            sys_range, dia_range = get_bp_fhir_ranges()

            parts = []
            worst = ComparisonResult.WITHIN_REPORTED_RANGE

            for component_val, component_name, fhir_rng in (
                (systolic, "Systolic", sys_range),
                (diastolic, "Diastolic", dia_range),
            ):
                if fhir_rng:
                    lo = fhir_rng["low"]
                    hi = fhir_rng["high"]
                    u = fhir_rng.get("unit", unit or "mmHg")
                    if component_val < lo:
                        comp = ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
                    elif component_val > hi:
                        comp = ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
                    else:
                        comp = ComparisonResult.WITHIN_REPORTED_RANGE
                    range_label = f"{_format_bound_num(lo)}–{_format_bound_num(hi)} {u}"
                    direction = (
                        "above" if comp == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
                        else "below" if comp == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
                        else "within"
                    )
                    parts.append(
                        f"{component_name} {_format_bound_num(component_val)} {u} "
                        f"is {direction} standard range ({range_label})"
                    )
                    if comp != ComparisonResult.WITHIN_REPORTED_RANGE:
                        worst = comp
                else:
                    parts.append(
                        f"{component_name} {_format_bound_num(component_val)} {unit or 'mmHg'} (no standard range)"
                    )

            significance = COMPARISON_SIGNIFICANCE_MAP.get(
                worst, SignificanceLevel.REQUIRES_CONTEXT
            )
            alert_level = map_to_alert(significance)
            return SignificanceResult(
                concept=concept_name,
                comparison=worst,
                significance=significance,
                alert_level=alert_level,
                basis="; ".join(parts) if parts else f"Blood pressure {raw_val} evaluated",
            )

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

        # --- LOINC+FHIR standard range fallback ---
        # When the PDF contains no reference range, attempt to resolve one
        # from the local FHIR ObservationDefinition bundle.
        # Unit conversion is applied so e.g. 98.6°F is compared against the
        # Celsius range (36.1–37.2°C) correctly.
        used_standard_range = False
        if comparison == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED:
            fhir_range = get_fhir_reference_range(concept_name, gender=gender)
            if fhir_range:
                low = fhir_range["low"]
                high = fhir_range["high"]
                range_unit = fhir_range.get("unit", "")
                # Convert extracted value to the range's unit if needed
                compare_val, effective_unit = prepare_for_comparison(
                    num_val, unit, range_unit
                )
                effective_unit = effective_unit or range_unit or unit or ""
                # Re-evaluate the comparison against the (unit-adjusted) FHIR range
                if compare_val is not None and low is not None and high is not None:
                    if compare_val < low:
                        comparison = ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
                    elif compare_val > high:
                        comparison = ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
                    else:
                        comparison = ComparisonResult.WITHIN_REPORTED_RANGE
                    significance = COMPARISON_SIGNIFICANCE_MAP.get(
                        comparison, SignificanceLevel.REQUIRES_CONTEXT
                    )
                    used_standard_range = True
                    # Use the converted value for display so the basis text
                    # shows the same unit as the range
                    num_val = compare_val
                    logger.debug(
                        "LOINC range applied for %r: %s–%s %s (LOINC %s)",
                        concept_name, low, high, effective_unit,
                        fhir_range.get("loinc_code", "?"),
                    )
        elif low is not None:
            # Reported range present — still normalize the display unit
            effective_unit = normalize_unit(unit or ref_unit or "") or effective_unit

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
                range_str = f"{low_str}–{high_str} %"
            elif effective_unit:
                range_str = f"{low_str}–{high_str} {effective_unit}"
            else:
                range_str = f"{low_str}–{high_str}"

            range_label = "standard reference range (LOINC)" if used_standard_range else "reported reference range"

            if comparison == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE:
                basis = f"Value {val_str} is above the {range_label} {range_str}"
            elif comparison == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE:
                basis = f"Value {val_str} is below the {range_label} {range_str}"
            else:
                basis = f"Value {val_str} is within the {range_label} {range_str}"

        # --- BMI category annotation ---
        _BMI_KEYWORDS = ("bmi", "body mass index")
        if any(k in concept_name.lower() for k in _BMI_KEYWORDS) and num_val is not None:
            bmi = num_val
            if bmi < 18.5:
                bmi_cat = "Underweight"
            elif bmi < 25.0:
                bmi_cat = "Normal weight"
            elif bmi < 30.0:
                bmi_cat = "Overweight"
            elif bmi < 35.0:
                bmi_cat = "Obese (Class I)"
            elif bmi < 40.0:
                bmi_cat = "Obese (Class II)"
            else:
                bmi_cat = "Severely obese (Class III)"
            basis = f"{basis} — Category: {bmi_cat}"

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
