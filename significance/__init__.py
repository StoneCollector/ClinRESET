"""
significance/__init__.py

Top-level package for clinical concept significance assessment.

Provides deterministic comparison against reported reference intervals,
triage alert levels, and structured clinical significance results.
"""

from __future__ import annotations

from significance.alerts import SIGNIFICANCE_ALERT_MAP, map_to_alert
from significance.classifier import (
    ASSERTION_SIGNIFICANCE_MAP,
    COMPARISON_SIGNIFICANCE_MAP,
    CRITICAL_OVERRIDES,
    classify_concept,
)
from significance.context import RELATIONSHIP_RULES, find_context
from significance.models import (
    AlertLevel,
    ComparisonResult,
    RelationshipType,
    SignificanceLevel,
    SignificanceResult,
)
from significance.range_engine import (
    compare_to_range,
    parse_numeric_value,
    parse_reference_bounds,
)

__all__ = [
    # Models and Enums
    "AlertLevel",
    "ComparisonResult",
    "RelationshipType",
    "SignificanceLevel",
    "SignificanceResult",
    # Functions
    "compare_to_range",
    "classify_concept",
    "find_context",
    "map_to_alert",
    "parse_numeric_value",
    "parse_reference_bounds",
    # Mappings and Rules
    "SIGNIFICANCE_ALERT_MAP",
    "ASSERTION_SIGNIFICANCE_MAP",
    "COMPARISON_SIGNIFICANCE_MAP",
    "CRITICAL_OVERRIDES",
    "RELATIONSHIP_RULES",
]
