"""
Unit tests for ClinRESET Interpretation and Significance Evaluation (Phase 6).
Verifies deterministic reference range comparisons, alert assignments,
and contextual non-causal clustering.
"""

import pytest
from src.interpretation.models import (
    AlertLevel,
    ComparisonResult,
    SignificanceLevel,
    SignificanceResult,
)
from src.interpretation.range_engine import (
    compare_to_range,
    parse_numeric_value,
    parse_reference_bounds,
)
from src.interpretation.classifier import ConceptClassifier
from src.interpretation.clusters import ContextClusterer
from src.interpretation.engine import ClinicalInterpreter


def test_parse_reference_bounds():
    # String format
    low, high, unit = parse_reference_bounds("06-11mm")
    assert low == 6.0
    assert high == 11.0
    assert unit == "mm"

    # Percentage format
    low, high, unit = parse_reference_bounds("55-74%")
    assert low == 55.0
    assert high == 74.0
    assert unit == "%"

    # Parentheses format
    low, high, unit = parse_reference_bounds("(12 - 16 g/dL)")
    assert low == 12.0
    assert high == 16.0
    assert unit == "g/dL"

    # Dict format
    low, high, unit = parse_reference_bounds({"low": 10, "high": 20, "unit": "cm"})
    assert low == 10.0
    assert high == 20.0
    assert unit == "cm"

    # Missing / None
    low, high, unit = parse_reference_bounds(None)
    assert low is None


def test_compare_to_range():
    # Within
    res = compare_to_range(8.5, "06-11mm")
    assert res == ComparisonResult.WITHIN_REPORTED_RANGE

    # Above
    res = compare_to_range(13.0, "06-11mm")
    assert res == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE

    # Below
    res = compare_to_range(45.0, "55-74%")
    assert res == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE

    # No range
    res = compare_to_range(34.0, None)
    assert res == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED


def test_classifier_quantitative_measurements():
    # 1. Above range (IVSd = 13 mm, ref 6-11mm) -> ORANGE
    res_above = ConceptClassifier.classify(
        concept="Interventricular Septum",
        value=13,
        unit="mm",
        reference_range="06-11mm",
    )
    assert res_above.significance == SignificanceLevel.OUTSIDE_REPORTED_RANGE
    assert res_above.alert_level == AlertLevel.ORANGE
    assert "above reported reference range" in res_above.basis

    # 2. Within range (EF = 60%, ref 55-74%) -> GREEN
    res_within = ConceptClassifier.classify(
        concept="Ejection Fraction",
        value=60,
        unit="%",
        reference_range="55-74%",
    )
    assert res_within.significance == SignificanceLevel.WITHIN_REPORTED_RANGE
    assert res_within.alert_level == AlertLevel.GREEN

    # 3. No range supplied (PASP = 34 mmHg) -> GREY
    res_no_range = ConceptClassifier.classify(
        concept="PASP",
        value=34,
        unit="mmHg",
        reference_range=None,
    )
    assert res_no_range.significance == SignificanceLevel.REQUIRES_CONTEXT
    assert res_no_range.alert_level == AlertLevel.GREY


def test_classifier_qualitative_findings():
    # 1. NORMAL finding -> GREEN
    res_normal = ConceptClassifier.classify(
        concept="Lung fields",
        assertion="NORMAL",
    )
    assert res_normal.significance == SignificanceLevel.INFORMATIONAL
    assert res_normal.alert_level == AlertLevel.GREEN

    # 2. ABSENT finding -> GREEN
    res_absent = ConceptClassifier.classify(
        concept="Pneumothorax",
        assertion="ABSENT",
    )
    assert res_absent.significance == SignificanceLevel.INFORMATIONAL
    assert res_absent.alert_level == AlertLevel.GREEN

    # 3. PRESENT finding (Notable) -> YELLOW
    res_present = ConceptClassifier.classify(
        concept="Disc bulge",
        assertion="PRESENT",
    )
    assert res_present.significance == SignificanceLevel.NOTABLE_FINDING
    assert res_present.alert_level == AlertLevel.YELLOW

    # 4. Critical life-threatening trigger -> RED
    res_crit = ConceptClassifier.classify(
        concept="Aortic Dissection",
        assertion="PRESENT",
    )
    assert res_crit.significance == SignificanceLevel.CRITICAL
    assert res_crit.alert_level == AlertLevel.RED


def test_context_clusters():
    # Echocardiography findings
    concepts = [
        "Concentric Left Ventricular Hypertrophy",
        "Interventricular Septum",
        "Left Ventricular Diastolic Dysfunction",
    ]
    clusters = ContextClusterer.find_clusters(concepts)
    assert len(clusters) >= 1
    assert "LVH" in clusters[0].cluster_name

    # Respiratory findings
    chest_concepts = ["Pleural effusion", "Consolidation"]
    chest_clusters = ContextClusterer.find_clusters(chest_concepts)
    assert len(chest_clusters) == 1
    assert "Pleuropulmonary" in chest_clusters[0].cluster_name


def test_full_report_interpretation():
    report_findings = [
        {"concept": "IVSd", "value": 13, "unit": "mm", "reference_range": "06-11mm"},
        {"concept": "EF", "value": 60, "unit": "%", "reference_range": "55-74%"},
        {"concept": "PASP", "value": 34, "unit": "mmHg"},
        {"concept": "Pneumothorax", "assertion": "ABSENT"},
        {"concept": "Disc bulge", "assertion": "PRESENT"},
    ]

    interp = ClinicalInterpreter.interpret_report(report_findings)

    assert len(interp.results) == 5
    assert interp.alert_counts[AlertLevel.ORANGE.value] == 1  # IVSd
    assert interp.alert_counts[AlertLevel.GREEN.value] == 2   # EF, Pneumothorax
    assert interp.alert_counts[AlertLevel.GREY.value] == 1    # PASP
    assert interp.alert_counts[AlertLevel.YELLOW.value] == 1  # Disc bulge
    assert interp.has_critical_alerts is False
