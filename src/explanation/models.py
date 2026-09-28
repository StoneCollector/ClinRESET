"""
Data models for ClinRESET Clinical Explanation layer (Phase 7).
Structures patient-friendly explanations, numerical verification outcomes,
and organized report sections without clinical speculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VerificationResult:
    """Outcome of numerical cross-checking between generated text and source facts."""
    is_valid: bool
    source_numbers: List[float] = field(default_factory=list)
    output_numbers: List[float] = field(default_factory=list)
    discrepancies: List[float] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "source_numbers": self.source_numbers,
            "output_numbers": self.output_numbers,
            "discrepancies": self.discrepancies,
            "reason": self.reason,
        }


@dataclass
class ConceptExplanation:
    """Patient-readable explanation for a single clinical concept or measurement."""
    concept: str
    preferred_term: str
    layman_synonym: Optional[str]
    assertion: str
    value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    alert_level: str = "GREEN"
    explanation_text: str = ""
    is_known: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept": self.concept,
            "preferred_term": self.preferred_term,
            "layman_synonym": self.layman_synonym,
            "assertion": self.assertion,
            "value": self.value,
            "unit": self.unit,
            "reference_range": self.reference_range,
            "alert_level": self.alert_level,
            "explanation_text": self.explanation_text,
            "is_known": self.is_known,
        }


@dataclass
class ExplanationSection:
    """A logical grouping of explanations for the patient."""
    title: str
    summary: str
    items: List[ConceptExplanation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class ReportExplanation:
    """Comprehensive patient explanation package for an entire clinical report."""
    patient_summary: str
    sections: List[ExplanationSection] = field(default_factory=list)
    questions_for_doctor: List[str] = field(default_factory=list)
    generation_mode: str = "deterministic_template"  # 'deterministic_template' | 'grounded_llm'
    verification: Optional[VerificationResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patient_summary": self.patient_summary,
            "sections": [s.to_dict() for s in self.sections],
            "questions_for_doctor": self.questions_for_doctor,
            "generation_mode": self.generation_mode,
            "verification": self.verification.to_dict() if self.verification else None,
        }
