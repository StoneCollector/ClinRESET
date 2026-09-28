"""
clinical_explanation/__init__.py

Phase 5A: Deterministic Clinical Explanation Engine.

Transforms Phase 4 structured clinical concepts into clear, patient-accessible
explanations without clinical interpretation, risk judgment, or diagnostic claims.
"""

from __future__ import annotations

from typing import Any

from clinical_explanation.explainer import ClinicalExplainer
from clinical_explanation.knowledge_base import ECHO_KNOWLEDGE_BASE, lookup_concept
from clinical_explanation.models import (
    ConceptExplanation,
    ExplanationSection,
    ExplanationStatus,
    ReportExplanations,
    UnavailabilityReason,
)
from clinical_explanation.renderer import (
    format_explanations_as_markdown,
    organize_explanations_into_sections,
    render_report_explanations,
)


def generate_clinical_explanations(
    structured_concepts: list[dict[str, Any]],
) -> ReportExplanations:
    """
    Generate deterministic clinical explanations from Phase 4 structured clinical concepts.

    Parameters
    ----------
    structured_concepts:
        List of concept dictionaries conforming to the Phase 4 -> Phase 5 contract.

    Returns
    -------
    ReportExplanations:
        Structured explanation records and organized categories.
    """
    explainer = ClinicalExplainer()
    explanations = explainer.explain_report_concepts(structured_concepts)
    return render_report_explanations(explanations)


__all__ = [
    "ClinicalExplainer",
    "ConceptExplanation",
    "ExplanationSection",
    "ReportExplanations",
    "ExplanationStatus",
    "UnavailabilityReason",
    "ECHO_KNOWLEDGE_BASE",
    "lookup_concept",
    "generate_clinical_explanations",
    "organize_explanations_into_sections",
    "render_report_explanations",
    "format_explanations_as_markdown",
]
