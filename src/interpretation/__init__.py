"""
ClinRESET Clinical Interpretation Package.
Provides deterministic reference range comparison, clinical significance classification,
alert triage indicators, and context clusters.
"""

from .models import (
    AlertLevel,
    ComparisonResult,
    FindingCluster,
    ReportInterpretation,
    SignificanceLevel,
    SignificanceResult,
)
from .range_engine import (
    compare_to_range,
    parse_numeric_value,
    parse_reference_bounds,
)
from .classifier import ConceptClassifier
from .clusters import ContextClusterer
from .engine import ClinicalInterpreter

__all__ = [
    "AlertLevel",
    "ComparisonResult",
    "FindingCluster",
    "ReportInterpretation",
    "SignificanceLevel",
    "SignificanceResult",
    "compare_to_range",
    "parse_numeric_value",
    "parse_reference_bounds",
    "ConceptClassifier",
    "ContextClusterer",
    "ClinicalInterpreter",
]
