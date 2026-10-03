"""
reporting/builder.py

Builds the visual, structured FinalReport from extraction and significance models.
"""

from __future__ import annotations

from typing import Any

from reporting.models import FinalReport
from significance.classifier import classify_concept
from significance.context import find_context
from significance.loinc_range_lookup import (
    get_bp_fhir_ranges,
    get_fhir_reference_range,
    get_patient_gender,
    is_blood_pressure_concept,
    parse_blood_pressure,
)
from significance.range_engine import parse_reference_bounds
from significance.unit_converter import prepare_for_comparison
from clinical_explanation.ollama_simplifier import generate_report_summary


def _measurement_entry(
    concept_name: str,
    value: Any,
    unit: Any,
    low: Any,
    high: Any,
    range_source: str,
    sig_res: Any,
    explanation_text: str,
    reference_range: Any = None,
) -> dict[str, Any]:
    """Build a single measurement dict for measurements_of_interest."""
    return {
        "concept": concept_name,
        "value": value,
        "unit": unit,
        "reference_range": reference_range,
        "low": low,
        "high": high,
        "range_source": range_source,
        "comparison": sig_res.comparison.value if hasattr(sig_res.comparison, "value") else str(sig_res.comparison),
        "alert_level": sig_res.alert_level.value if hasattr(sig_res.alert_level, "value") else str(sig_res.alert_level),
        "significance": sig_res.significance.value if hasattr(sig_res.significance, "value") else str(sig_res.significance),
        "basis": sig_res.basis,
        "explanation": explanation_text,
    }

DEFAULT_LIMITATIONS = [
    "This report is generated using deterministic, rule-based extraction and standardized clinical knowledge-base definitions.",
    "It does not provide medical diagnoses, treatment recommendations, prognosis, or clinical risk assessments.",
    "All interpretations, classifications, and explanations should be reviewed by a qualified healthcare professional.",
    "Reference intervals and measurements reflect the source report where available. When the source document does not include a reference range, a standard adult interval is sourced from a LOINC+FHIR R4 ObservationDefinition bundle (based on HL7, AACC, and WHO published guidelines). These standard ranges may not apply to all individuals; consult your clinician.",
]


def build_final_report(report_json: dict[str, Any]) -> FinalReport:
    """
    Construct a FinalReport from the normalized extraction output dictionary.

    Parameters
    ----------
    report_json:
        Normalized report dictionary conforming to the output/report.json schema.

    Returns
    -------
    FinalReport:
        Assembled final report with summary, key findings, measurements, context, and limitations.
    """
    classification = report_json.get("classification") or {}
    report_summary = {
        "report_type": classification.get("report_type", "unknown"),
        "status": classification.get("status", "unknown"),
        "confidence": classification.get("confidence", 0.0),
    }

    clinical_info = report_json.get("clinical_information") or {}
    concepts = clinical_info.get("structured_clinical_concepts") or []
    explanations = clinical_info.get("explanations") or []

    # Extract patient gender for gender-aware LOINC range selection
    patient_gender = get_patient_gender(report_json)
    patient_context = {"gender": patient_gender} if patient_gender else {}

    # Map explanation by concept name
    exp_map: dict[str, str] = {}
    for exp in explanations:
        c_name = exp.get("concept") or exp.get("original_text")
        if c_name and exp.get("explanation"):
            exp_map[c_name] = exp["explanation"]

    key_findings: list[dict[str, Any]] = []
    measurements_of_interest: list[dict[str, Any]] = []
    sig_results = []

    # Filter out non-clinical administrative concepts (e.g., "Registered on",
    # "UHID", "Reg. no.") before building the report. These should have been
    # caught upstream but this is a final defensive layer.
    try:
        from clinical_extraction.filters import is_admin_field, is_date_artefact
        def _is_junk_concept(c: dict) -> bool:
            name = c.get("concept") or c.get("original_text") or ""
            value = c.get("value")
            unit = c.get("unit")
            return is_admin_field(name) or is_date_artefact(name, value, unit)
        concepts = [c for c in concepts if not _is_junk_concept(c)]
    except ImportError:
        pass

    for c in concepts:
        sig_res = classify_concept(c, patient_context=patient_context)
        sig_results.append(sig_res)

        concept_name = c.get("concept") or c.get("original_text") or "Unknown Concept"
        explanation_text = exp_map.get(concept_name) or exp_map.get(c.get("original_text", "")) or ""

        # Differentiate quantitative measurements from qualitative findings
        is_measurement = c.get("value") is not None or c.get("type") == "MEASUREMENT"

        if is_measurement:
            raw_val = c.get("value")

            # ----------------------------------------------------------------
            # Special case: compound blood pressure "118/76" → two rows
            # ----------------------------------------------------------------
            if is_blood_pressure_concept(concept_name):
                bp = parse_blood_pressure(str(raw_val) if raw_val is not None else "")
                if bp:
                    systolic, diastolic = bp
                    sys_range, dia_range = get_bp_fhir_ranges()
                    unit_str = c.get("unit") or "mmHg"

                    measurements_of_interest.append(_measurement_entry(
                        concept_name=f"{concept_name} (Systolic)",
                        value=systolic,
                        unit=unit_str,
                        low=sys_range["low"] if sys_range else None,
                        high=sys_range["high"] if sys_range else None,
                        range_source="loinc_standard" if sys_range else "none",
                        sig_res=sig_res,
                        explanation_text=explanation_text,
                    ))
                    measurements_of_interest.append(_measurement_entry(
                        concept_name=f"{concept_name} (Diastolic)",
                        value=diastolic,
                        unit=unit_str,
                        low=dia_range["low"] if dia_range else None,
                        high=dia_range["high"] if dia_range else None,
                        range_source="loinc_standard" if dia_range else "none",
                        sig_res=sig_res,
                        explanation_text=explanation_text,
                    ))
                    continue  # skip the generic measurement path below

            # ----------------------------------------------------------------
            # Generic measurement: use reported range or LOINC fallback
            # ----------------------------------------------------------------
            low, high, ref_unit = parse_reference_bounds(c.get("reference_range"))
            effective_unit = c.get("unit") or ref_unit
            range_source = "reported"

            if low is None or high is None:
                fhir_range = get_fhir_reference_range(concept_name)
                if fhir_range:
                    low = fhir_range["low"]
                    high = fhir_range["high"]
                    range_unit = fhir_range.get("unit", "")
                    # Convert value to the range's unit (e.g. °F → °C)
                    # so the SVG range bar shows matching numbers
                    from significance.range_engine import parse_numeric_value
                    num_val_f = parse_numeric_value(raw_val)
                    if num_val_f is not None:
                        converted_val, effective_unit = prepare_for_comparison(
                            num_val_f, effective_unit, range_unit
                        )
                        raw_val = converted_val  # store converted for the bar
                        effective_unit = effective_unit or range_unit
                    else:
                        effective_unit = effective_unit or range_unit
                    range_source = "loinc_standard"

            measurements_of_interest.append(_measurement_entry(
                concept_name=concept_name,
                value=raw_val,
                unit=effective_unit,
                low=low,
                high=high,
                range_source=range_source,
                sig_res=sig_res,
                explanation_text=explanation_text,
                reference_range=c.get("reference_range"),
            ))
        else:
            key_findings.append({
                "concept": concept_name,
                "assertion": c.get("assertion", "PRESENT"),
                "alert_level": sig_res.alert_level.value if hasattr(sig_res.alert_level, "value") else str(sig_res.alert_level),
                "significance": sig_res.significance.value if hasattr(sig_res.significance, "value") else str(sig_res.significance),
                "basis": sig_res.basis,
                "explanation": explanation_text,
                "modifiers": c.get("modifiers") or {},
                "related_anatomy": c.get("related_anatomy") or [],
            })

    # Find context groupings
    context_groups = find_context(concepts, sig_results)
    serialized_context: list[dict[str, Any]] = []
    for g in context_groups:
        serialized_context.append({
            "concepts": list(g.get("concepts", [])),
            "relationship": g.get("relationship", "RELATED_FINDINGS"),
            "explanation": g.get("explanation", ""),
        })

    # Generate overall report summary
    overall_summary = generate_report_summary(
        report_type=report_summary["report_type"],
        measurements=measurements_of_interest,
        findings=key_findings,
    )
    if overall_summary:
        report_summary["overall_summary"] = overall_summary

    return FinalReport(
        report_summary=report_summary,
        key_findings=key_findings,
        measurements_of_interest=measurements_of_interest,
        context=serialized_context,
        limitations=list(DEFAULT_LIMITATIONS),
    )
