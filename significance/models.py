"""
significance/models.py

Data models and enumerations for clinical concept significance assessment.

Defines standardized comparison results against reported reference intervals,
significance levels, alert categories, and the structured evaluation result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ComparisonResult(str, Enum):
    """Result of comparing a quantitative measurement against a reported reference range."""

    WITHIN_REPORTED_RANGE = "WITHIN_REPORTED_RANGE"
    ABOVE_REPORTED_REFERENCE_RANGE = "ABOVE_REPORTED_REFERENCE_RANGE"
    BELOW_REPORTED_REFERENCE_RANGE = "BELOW_REPORTED_REFERENCE_RANGE"
    NO_REFERENCE_RANGE_SUPPLIED = "NO_REFERENCE_RANGE_SUPPLIED"


class SignificanceLevel(str, Enum):
    """Categorical significance classification for a clinical concept or measurement."""

    INFORMATIONAL = "INFORMATIONAL"
    WITHIN_REPORTED_RANGE = "WITHIN_REPORTED_RANGE"
    OUTSIDE_REPORTED_RANGE = "OUTSIDE_REPORTED_RANGE"
    NOTABLE_FINDING = "NOTABLE_FINDING"
    REQUIRES_CONTEXT = "REQUIRES_CONTEXT"
    UNRESOLVED = "UNRESOLVED"
    CRITICAL = "CRITICAL"


class AlertLevel(str, Enum):
    """Visual or prioritized triage indicator associated with concept significance."""

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"
    GREY = "GREY"


class RelationshipType(str, Enum):
    """Types of non-causal contextual relationships between clinical findings."""

    RELATED_FINDINGS = "RELATED_FINDINGS"


@dataclass
class SignificanceResult:
    """
    Structured outcome of evaluating the clinical significance of a single concept.

    Attributes
    ----------
    concept:
        The normalized or surface name of the evaluated concept.
    comparison:
        The comparison status against the reported reference interval.
    significance:
        Categorical significance level.
    alert_level:
        Triage alert indicator (GREEN, YELLOW, ORANGE, RED, GREY).
    basis:
        Short, purely factual explanation of WHY this classification was assigned.
    """

    concept: str
    comparison: ComparisonResult
    significance: SignificanceLevel
    alert_level: AlertLevel
    basis: str

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a plain dictionary suitable for serialization."""
        return {
            "concept": self.concept,
            "comparison": self.comparison.value if hasattr(self.comparison, "value") else str(self.comparison),
            "significance": self.significance.value if hasattr(self.significance, "value") else str(self.significance),
            "alert_level": self.alert_level.value if hasattr(self.alert_level, "value") else str(self.alert_level),
            "basis": self.basis,
        }
