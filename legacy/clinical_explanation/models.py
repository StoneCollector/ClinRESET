"""
clinical_explanation/models.py

Data models for the deterministic clinical explanation layer (Phase 5A).

These models structure patient-readable explanations generated from Phase 4
structured clinical concepts without clinical diagnosis, risk assessment,
or prognostic extrapolations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class ExplanationStatus:
    """Status indicating whether a concept was successfully explained."""

    EXPLAINED = "EXPLAINED"
    EXPLANATION_UNAVAILABLE = "EXPLANATION_UNAVAILABLE"


class UnavailabilityReason:
    """Controlled reasons when an explanation cannot be provided."""

    UNKNOWN_CONCEPT = "UNKNOWN_CONCEPT"
    AMBIGUOUS_CONCEPT = "AMBIGUOUS_CONCEPT"
    NOT_IN_KNOWLEDGE_BASE = "NOT_IN_KNOWLEDGE_BASE"


@dataclass
class ConceptExplanation:
    """
    Patient-readable explanation for a single structured clinical concept.

    Preserves exact surface text, values, units, reference ranges, assertions,
    modifiers, related anatomy, and provenance from Phase 4.
    """

    concept: str
    original_text: str
    type: str
    semantic_category: str
    assertion: str
    value: Optional[Any] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    related_anatomy: list[str] = field(default_factory=list)
    modifiers: dict[str, Any] = field(default_factory=dict)
    status: str = ExplanationStatus.EXPLAINED
    explanation: Optional[str] = None
    unavailability_reason: Optional[str] = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to plain dictionary suitable for JSON serialization in report.json."""
        d: dict[str, Any] = {
            "concept": self.concept,
            "original_text": self.original_text,
            "type": self.type,
            "semantic_category": self.semantic_category,
            "assertion": self.assertion,
            "value": self.value,
            "unit": self.unit,
            "reference_range": self.reference_range,
            "related_anatomy": list(self.related_anatomy),
            "modifiers": dict(self.modifiers),
            "status": self.status,
            "explanation": self.explanation,
            "provenance": dict(self.provenance),
        }
        if self.unavailability_reason:
            d["unavailability_reason"] = self.unavailability_reason
        return d


@dataclass
class ExplanationSection:
    """An organized category grouping related concept explanations."""

    title: str
    category: str
    explanations: list[ConceptExplanation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert section to dictionary."""
        return {
            "title": self.title,
            "category": self.category,
            "explanations": [e.to_dict() for e in self.explanations],
        }


@dataclass
class ReportExplanations:
    """Complete collection of explanations and organized sections for a report."""

    explanations: list[ConceptExplanation] = field(default_factory=list)
    sections: list[ExplanationSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "explanations": [e.to_dict() for e in self.explanations],
            "sections": [s.to_dict() for s in self.sections],
        }
