"""
Data models and enumerations for ClinRESET Clinical Concept Interpretation and Significance Assessment.

Defines standardized comparison results against reported reference intervals,
significance levels, alert categories, and structured evaluation outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ComparisonResult(str, Enum):
    """Result of comparing a quantitative measurement against a reported reference range."""
    WITHIN_REPORTED_RANGE = "WITHIN_REPORTED_RANGE"
    ABOVE_REPORTED_REFERENCE_RANGE = "ABOVE_REPORTED_REFERENCE_RANGE"
    BELOW_REPORTED_REFERENCE_RANGE = "BELOW_REPORTED_REFERENCE_RANGE"
    NO_REFERENCE_RANGE_SUPPLIED = "NO_REFERENCE_RANGE_SUPPLIED"


class SignificanceLevel(str, Enum):
    """Categorical significance classification for a clinical concept or measurement."""
    INFORMATIONAL = "INFORMATIONAL"              # Normal finding or explicitly absent
    WITHIN_REPORTED_RANGE = "WITHIN_REPORTED_RANGE"  # Metric falls inside reference range
    OUTSIDE_REPORTED_RANGE = "OUTSIDE_REPORTED_RANGE" # Metric violates reference range
    NOTABLE_FINDING = "NOTABLE_FINDING"          # Qualitative finding present (e.g. disc bulge)
    REQUIRES_CONTEXT = "REQUIRES_CONTEXT"        # Measurement without range (e.g. PASP=34)
    UNRESOLVED = "UNRESOLVED"                    # Ambiguous or indeterminate finding
    CRITICAL = "CRITICAL"                        # Life-threatening finding requiring immediate alert


class AlertLevel(str, Enum):
    """Visual or prioritized triage indicator associated with concept significance."""
    GREEN = "GREEN"      # Normal / Reassuring / Inside Range
    YELLOW = "YELLOW"    # Notable Finding / Clinician Awareness
    ORANGE = "ORANGE"    # Outside Reference Range (Objective deviation)
    RED = "RED"          # Critical Emergency Alert
    GREY = "GREY"        # Requires Patient Context / Isolated metric


@dataclass
class SignificanceResult:
    """
    Structured outcome of evaluating the clinical significance of a single concept or measurement.
    """
    concept: str
    comparison: ComparisonResult
    significance: SignificanceLevel
    alert_level: AlertLevel
    basis: str
    value: Optional[float] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept": self.concept,
            "comparison": self.comparison.value if hasattr(self.comparison, "value") else str(self.comparison),
            "significance": self.significance.value if hasattr(self.significance, "value") else str(self.significance),
            "alert_level": self.alert_level.value if hasattr(self.alert_level, "value") else str(self.alert_level),
            "basis": self.basis,
            "value": self.value,
            "unit": self.unit,
            "reference_range": self.reference_range,
        }


@dataclass
class FindingCluster:
    """A non-causal contextual group of clinically related findings reported together."""
    cluster_name: str
    matched_concepts: List[str]
    organ_system: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_name": self.cluster_name,
            "matched_concepts": self.matched_concepts,
            "organ_system": self.organ_system,
            "explanation": self.explanation,
        }


@dataclass
class ReportInterpretation:
    """Comprehensive interpretation summary for an entire clinical report."""
    results: List[SignificanceResult] = field(default_factory=list)
    clusters: List[FindingCluster] = field(default_factory=list)
    alert_counts: Dict[str, int] = field(default_factory=dict)
    has_critical_alerts: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "clusters": [c.to_dict() for c in self.clusters],
            "alert_counts": self.alert_counts,
            "has_critical_alerts": self.has_critical_alerts,
        }
