"""
reporting/builder.py

Builds the visual, structured FinalReport from extraction and significance models.
"""

from __future__ import annotations

from typing import Any

from reporting.models import FinalReport
from significance.classifier import classify_concept
from significance.context import find_context
from significance.range_engine import parse_reference_bounds

DEFAULT_LIMITATIONS = [
    "This report is generated using deterministic, rule-based extraction and standardized clinical knowledge-base definitions.",
    "It does not provide medical diagnoses, treatment recommendations, prognosis, or clinical risk assessments.",
    "All interpretations, classifications, and explanations should be reviewed by a qualified healthcare professional.",
    "Reference intervals and measurements reflect the source report and may vary across laboratories or clinical contexts.",
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

    # Map explanation by concept name
    exp_map: dict[str, str] = {}
    for exp in explanations:
        c_name = exp.get("concept") or exp.get("original_text")
        if c_name and exp.get("explanation"):
            exp_map[c_name] = exp["explanation"]

    key_findings: list[dict[str, Any]] = []
    measurements_of_interest: list[dict[str, Any]] = []
    sig_results = []

    for c in concepts:
        sig_res = classify_concept(c)
        sig_results.append(sig_res)

        concept_name = c.get("concept") or c.get("original_text") or "Unknown Concept"
        explanation_text = exp_map.get(concept_name) or exp_map.get(c.get("original_text", "")) or ""

        # Differentiate quantitative measurements from qualitative findings
        is_measurement = c.get("value") is not None or c.get("type") == "MEASUREMENT"

        if is_measurement:
            low, high, ref_unit = parse_reference_bounds(c.get("reference_range"))
            measurements_of_interest.append({
                "concept": concept_name,
                "value": c.get("value"),
                "unit": c.get("unit") or ref_unit,
                "reference_range": c.get("reference_range"),
                "low": low,
                "high": high,
                "comparison": sig_res.comparison.value if hasattr(sig_res.comparison, "value") else str(sig_res.comparison),
                "alert_level": sig_res.alert_level.value if hasattr(sig_res.alert_level, "value") else str(sig_res.alert_level),
                "significance": sig_res.significance.value if hasattr(sig_res.significance, "value") else str(sig_res.significance),
                "basis": sig_res.basis,
                "explanation": explanation_text,
            })
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

    return FinalReport(
        report_summary=report_summary,
        key_findings=key_findings,
        measurements_of_interest=measurements_of_interest,
        context=serialized_context,
        limitations=list(DEFAULT_LIMITATIONS),
    )
