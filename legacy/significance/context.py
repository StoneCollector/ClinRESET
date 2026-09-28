"""
significance/context.py

Report-level relationship grouping between already-classified concepts.

Groups findings that are already explicitly present in the report under shared,
hand-defined non-causal relationship rules without inference, similarity scoring,
or embedding models.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from significance.models import RelationshipType, SignificanceResult

logger = logging.getLogger("significance.context")

# ---------------------------------------------------------------------------
# Hand-defined relationship rules
# ---------------------------------------------------------------------------
# Strict constraints:
# - Matches explicit concept name substrings (case-insensitive)
# - Requires at least 2 matching concepts in the report to trigger
# - Explanations describe co-occurrence in standard echocardiographic assessment
#   and explicitly avoid asserting causation or diagnostic consequence.
RELATIONSHIP_RULES: list[dict[str, Any]] = [
    {
        "name": "concentric_lvh_cluster",
        "concepts": [
            "Concentric Left Ventricular Hypertrophy",
            "Interventricular Septum Thickness",
            "Left Ventricular Diastolic Dysfunction",
        ],
        "relationship": RelationshipType.RELATED_FINDINGS,
        "explanation": (
            "These findings were all reported together and commonly co-occur in "
            "echocardiographic assessment of ventricular structure and function; "
            "the report does not establish that one caused another."
        ),
    },
    {
        "name": "left_ventricular_systolic_function_cluster",
        "concepts": [
            "Ejection Fraction",
            "Fractional Shortening",
            "Left Ventricular Function",
        ],
        "relationship": RelationshipType.RELATED_FINDINGS,
        "explanation": (
            "These parameters and observations all evaluate the systolic contraction "
            "and pumping capacity of the left ventricle; they are reported in parallel "
            "without implying a causal hierarchy."
        ),
    },
    {
        "name": "pulmonary_hemodynamic_cluster",
        "concepts": [
            "Tricuspid Regurgitation",
            "Pulmonary Artery Systolic Pressure",
            "Right Ventricular Function",
        ],
        "relationship": RelationshipType.RELATED_FINDINGS,
        "explanation": (
            "These findings and measurements reflect right-heart and pulmonary "
            "circulation hemodynamics routinely evaluated together during Doppler "
            "examination; the report does not establish that one caused another."
        ),
    },
]


def find_context(
    concepts: Optional[list[dict[str, Any]]] = None,
    results: Optional[list[SignificanceResult]] = None,
) -> list[dict[str, Any]]:
    """
    Identify report-level contextual groupings among explicitly present concepts.

    Parameters
    ----------
    concepts:
        List of structured concept dictionaries from the normalized report.
    results:
        List of already-evaluated SignificanceResult objects (optional).

    Returns
    -------
    list[dict[str, Any]]
        List of matched context entries:
        {
            "concepts": [<matched concept names as they actually appear in the report>],
            "relationship": <RelationshipType>,
            "explanation": <template text>
        }
    """
    if concepts is None:
        concepts = []
    if results is None:
        results = []

    # Extract all concept names present in the report
    report_concepts: list[str] = []

    if concepts:
        for c in concepts:
            if isinstance(c, dict):
                name = c.get("concept") or c.get("original_text")
                if name and isinstance(name, str) and name not in report_concepts:
                    report_concepts.append(name)
    elif results:
        for r in results:
            if hasattr(r, "concept") and r.concept and r.concept not in report_concepts:
                report_concepts.append(r.concept)

    if not report_concepts:
        return []

    context_entries: list[dict[str, Any]] = []

    for rule in RELATIONSHIP_RULES:
        rule_concept_patterns: list[str] = rule.get("concepts", [])
        matched_concepts: list[str] = []
        matched_lower_set: set[str] = set()

        for pattern in rule_concept_patterns:
            pat_clean = pattern.strip().lower()
            if not pat_clean:
                continue

            for r_name in report_concepts:
                if pat_clean in r_name.lower():
                    if r_name.lower() not in matched_lower_set:
                        matched_concepts.append(r_name)
                        matched_lower_set.add(r_name.lower())

        # At least 2 of its listed concept substrings must be present to form a group
        if len(matched_concepts) >= 2:
            context_entries.append(
                {
                    "concepts": matched_concepts,
                    "relationship": rule.get("relationship", RelationshipType.RELATED_FINDINGS),
                    "explanation": rule.get("explanation", ""),
                }
            )

    return context_entries
