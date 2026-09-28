"""
clinical_explanation/renderer.py

Organizes and formats clinical explanations into structured categories and
patient-friendly summaries.
"""

from __future__ import annotations

from typing import Optional

from clinical_explanation.models import (
    ConceptExplanation,
    ExplanationSection,
    ReportExplanations,
)

# Standard section mapping from semantic category
CATEGORY_SECTION_MAP = {
    "FUNCTION": ("Heart Function", 1),
    "STRUCTURAL_FINDING": ("Heart Structure", 2),
    "MEASUREMENT": ("Heart Dimensions & Thickness", 3),
    "WALL_MOTION": ("Wall Motion", 4),
    "DIASTOLIC_FUNCTION": ("Diastolic Function", 5),
    "VALVULAR_FINDING": ("Valvular Findings", 6),
    "PRESSURE": ("Pressure and Doppler", 7),
    "DOPPLER_MEASUREMENT": ("Pressure and Doppler", 7),
    "THROMBUS": ("Other Findings", 8),
    "EFFUSION": ("Other Findings", 8),
    "OTHER_CLINICAL": ("Other Findings", 8),
}


def organize_explanations_into_sections(
    explanations: list[ConceptExplanation],
) -> list[ExplanationSection]:
    """
    Group explanations into stable, standardized report sections based on their
    semantic categories.
    """
    sections_dict: dict[str, list[ConceptExplanation]] = {}

    for exp in explanations:
        sec_name, _ = CATEGORY_SECTION_MAP.get(exp.semantic_category, ("Other Findings", 99))
        sections_dict.setdefault(sec_name, []).append(exp)

    # Sort sections in canonical order
    order_map = {
        "Heart Function": 1,
        "Heart Structure": 2,
        "Heart Dimensions & Thickness": 3,
        "Wall Motion": 4,
        "Diastolic Function": 5,
        "Valvular Findings": 6,
        "Pressure and Doppler": 7,
        "Other Findings": 8,
    }

    sections: list[ExplanationSection] = []
    for title in sorted(sections_dict.keys(), key=lambda t: order_map.get(t, 99)):
        items = sections_dict[title]
        category = items[0].semantic_category if items else "GENERAL"
        sections.append(
            ExplanationSection(
                title=title,
                category=category,
                explanations=items,
            )
        )

    return sections


def render_report_explanations(
    explanations: list[ConceptExplanation],
) -> ReportExplanations:
    """Produce the complete ReportExplanations object with organized sections."""
    sections = organize_explanations_into_sections(explanations)
    return ReportExplanations(
        explanations=explanations,
        sections=sections,
    )


def format_explanations_as_markdown(report_explanations: ReportExplanations) -> str:
    """Render explanations into clean, patient-readable Markdown."""
    lines: list[str] = ["# Clinical Report Explanations (Phase 5A)", ""]

    for sec in report_explanations.sections:
        lines.append(f"## {sec.title}")
        lines.append("")
        for exp in sec.explanations:
            prefix = f"**{exp.concept}**"
            if exp.value is not None:
                unit_str = f" {exp.unit}" if exp.unit else ""
                prefix += f" ({exp.value}{unit_str})"
            lines.append(f"- {prefix}: {exp.explanation}")
        lines.append("")

    return "\n".join(lines).strip()
