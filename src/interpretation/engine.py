"""
Unified Clinical Interpretation Engine for ClinRESET.
Orchestrates reference range comparisons, severity classification,
triage alert levels, and context cluster identification across full reports.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .classifier import ConceptClassifier
from .clusters import ContextClusterer
from .models import AlertLevel, FindingCluster, ReportInterpretation, SignificanceResult

logger = logging.getLogger(__name__)


class ClinicalInterpreter:
    """Evaluates findings in a report against reported reference ranges and assertions."""

    @classmethod
    def interpret_finding(
        cls,
        concept: str,
        assertion: str = "PRESENT",
        value: Optional[Any] = None,
        unit: Optional[str] = None,
        reference_range: Optional[Any] = None,
        source_text: Optional[str] = None,
    ) -> SignificanceResult:
        """Evaluates a single clinical finding or measurement."""
        return ConceptClassifier.classify(
            concept=concept,
            assertion=assertion,
            value=value,
            unit=unit,
            reference_range=reference_range,
            source_text=source_text,
        )

    @classmethod
    def interpret_report(
        cls,
        findings: List[Dict[str, Any]],
    ) -> ReportInterpretation:
        """
        Interprets a full collection of report findings.

        Args:
            findings: List of dicts, each with keys like:
                'concept', 'assertion', 'value', 'unit', 'reference_range', 'source_text'
        """
        results: List[SignificanceResult] = []
        concepts_present: List[str] = []
        alert_counts: Dict[str, int] = {level.value: 0 for level in AlertLevel}

        for item in findings:
            concept = item.get("concept") or item.get("preferred_term") or item.get("original_text") or "Unknown"
            assertion = item.get("assertion", "PRESENT")
            val = item.get("value")
            unit = item.get("unit")
            ref_range = item.get("reference_range")
            source_text = item.get("source_text") or item.get("clause")

            res = cls.interpret_finding(
                concept=concept,
                assertion=assertion,
                value=val,
                unit=unit,
                reference_range=ref_range,
                source_text=source_text,
            )
            results.append(res)

            alert_str = res.alert_level.value
            alert_counts[alert_str] = alert_counts.get(alert_str, 0) + 1

            if concept not in concepts_present:
                concepts_present.append(concept)

        # Context clustering
        clusters: List[FindingCluster] = ContextClusterer.find_clusters(concepts_present)
        has_critical = alert_counts.get(AlertLevel.RED.value, 0) > 0

        return ReportInterpretation(
            results=results,
            clusters=clusters,
            alert_counts=alert_counts,
            has_critical_alerts=has_critical,
        )
