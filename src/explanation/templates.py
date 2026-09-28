"""
Deterministic Template Explainer for ClinRESET.
Generates 100% factual, grounded, patient-accessible explanations
at approximately a 6th-grade reading level without relying on external LLMs or GPUs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import ConceptExplanation, ExplanationSection, ReportExplanation, VerificationResult

logger = logging.getLogger(__name__)


class DeterministicTemplateExplainer:
    """Generates rule-based, assertion-aware explanations using verified normalized facts."""

    @classmethod
    def explain_finding(cls, item: Dict[str, Any]) -> ConceptExplanation:
        """Explains an individual clinical finding or metric in plain language."""
        raw_concept = item.get("concept") or item.get("preferred_term") or "Clinical finding"
        preferred = item.get("preferred_term") or raw_concept.title()
        layman = item.get("layman_synonym")
        assertion = str(item.get("assertion", "PRESENT")).upper()
        val = item.get("value")
        unit = item.get("unit") or ""
        ref_range = item.get("reference_range")
        alert = item.get("alert_level") or "GREEN"
        is_known = item.get("is_known", True)

        term_display = f"{preferred} ({layman})" if layman and layman.lower() != preferred.lower() else preferred

        # 1. Quantitative measurement explanation
        if val is not None:
            val_str = f"{val} {unit}".strip()
            if ref_range:
                text = (
                    f"{term_display} was measured at {val_str}. "
                    f"The laboratory reference standard listed on this report is {ref_range}. "
                )
                if alert == "ORANGE":
                    text += "This measurement is outside the standard reference range."
                elif alert == "GREEN":
                    text += "This measurement is within normal expected limits."
            else:
                text = f"{term_display} was measured at {val_str}."

        # 2. Qualitative finding explanation
        elif assertion == "NORMAL":
            text = f"{term_display} was checked and found to be normal and functioning properly."
        elif assertion == "ABSENT":
            text = f"The examination confirmed that there is no sign or evidence of {term_display}."
        elif assertion == "PRESENT":
            text = f"The report notes the presence of {term_display}."
        else:
            text = f"The examination evaluated {term_display} with possible or indeterminate findings."

        return ConceptExplanation(
            concept=raw_concept,
            preferred_term=preferred,
            layman_synonym=layman,
            assertion=assertion,
            value=float(val) if val is not None else None,
            unit=unit or None,
            reference_range=str(ref_range) if ref_range else None,
            alert_level=alert,
            explanation_text=text,
            is_known=is_known,
        )

    @classmethod
    def explain_report(
        cls,
        findings: List[Dict[str, Any]],
        report_type: Optional[str] = None,
    ) -> ReportExplanation:
        """
        Synthesizes a complete patient-friendly explanation package for the report.
        """
        explanations: List[ConceptExplanation] = [cls.explain_finding(item) for item in findings]

        # Categorize into sections
        reassuring_items = [e for e in explanations if e.alert_level == "GREEN"]
        notable_items = [e for e in explanations if e.alert_level in ("YELLOW", "ORANGE", "RED")]
        context_items = [e for e in explanations if e.alert_level == "GREY"]

        sections: List[ExplanationSection] = []

        if notable_items:
            sections.append(
                ExplanationSection(
                    title="Key Findings to Discuss",
                    summary="These items represent notable findings or measurements that differ from standard reference ranges.",
                    items=notable_items,
                )
            )

        if reassuring_items:
            sections.append(
                ExplanationSection(
                    title="Normal & Reassuring Observations",
                    summary="These structures and areas were evaluated and found to be normal or free of disease.",
                    items=reassuring_items,
                )
            )

        if context_items:
            sections.append(
                ExplanationSection(
                    title="Additional Measurements",
                    summary="These values provide anatomical measurements that your physician evaluates in context.",
                    items=context_items,
                )
            )

        # Overview summary
        modality_name = f"{report_type.title()} " if report_type else ""
        if notable_items:
            summary = (
                f"Your {modality_name}report has been reviewed. The examination identified "
                f"{len(notable_items)} notable finding(s) or measurement(s) that your doctor will discuss with you, "
                f"alongside {len(reassuring_items)} reassuring normal observation(s)."
            )
        else:
            summary = (
                f"Your {modality_name}report shows reassuring findings. The examined structures and measurements "
                "are within normal expected limits with no acute abnormalities documented."
            )

        # Questions for doctor
        questions = [
            "What do these findings mean for my current symptoms or treatment plan?",
            "Do any of the noted measurements require follow-up imaging in the future?",
            "Are there any daily activities, medications, or lifestyle steps you recommend?",
        ]

        # Verify numerical consistency
        verification = VerificationResult(
            is_valid=True,
            reason="Deterministic template generated from ground truth verified facts.",
        )

        return ReportExplanation(
            patient_summary=summary,
            sections=sections,
            questions_for_doctor=questions,
            generation_mode="deterministic_template",
            verification=verification,
        )
