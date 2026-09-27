"""
tests/test_significance.py

Comprehensive test suite for the significance assessment package.

Covers:
1. range_engine: inclusive comparisons, bounds extraction, int/float/str inputs,
   missing ranges, boundary equalities, malformed inputs & warning logging.
2. alerts: static dict mapping and triage alert categories.
3. classifier: structured concept evaluation, assertion mappings, basis strings,
   absence of auto-assigned critical findings.
4. real report validation: evaluation of every concept in sample_report report.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import pytest

from significance import (
    AlertLevel,
    ASSERTION_SIGNIFICANCE_MAP,
    COMPARISON_SIGNIFICANCE_MAP,
    ComparisonResult,
    CRITICAL_OVERRIDES,
    SignificanceLevel,
    SignificanceResult,
    classify_concept,
    compare_to_range,
    map_to_alert,
    parse_numeric_value,
    parse_reference_bounds,
)

REPORT_JSON_PATH = Path("output") / "sample_report" / "normalized" / "report.json"


# ===========================================================================
# 1. RANGE ENGINE TESTS
# ===========================================================================

class TestRangeEngine:
    """Unit tests for significance/range_engine.py."""

    def test_within_range_dict(self):
        # Dict with low and high
        ref = {"low": 20, "high": 37}
        assert compare_to_range(25, ref) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range(20.5, ref) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range("30", ref) == ComparisonResult.WITHIN_REPORTED_RANGE

    def test_within_range_string(self):
        # String format range
        assert compare_to_range(60, "55-74%") == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range(32.5, "28-40%") == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range(25, "20-37mm") == ComparisonResult.WITHIN_REPORTED_RANGE

    def test_above_range(self):
        ref = {"low": 6, "high": 11}
        assert compare_to_range(13, ref) == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
        assert compare_to_range(11.1, ref) == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
        assert compare_to_range("15", ref) == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
        assert compare_to_range(13, "06-11mm") == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE

    def test_below_range(self):
        ref = {"low": 28, "high": 40}
        assert compare_to_range(20, ref) == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
        assert compare_to_range(27.9, ref) == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
        assert compare_to_range("15", ref) == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
        assert compare_to_range(5, "06-11mm") == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE

    def test_boundary_equal_to_low(self):
        # Inclusive comparison: equal to low must be WITHIN_REPORTED_RANGE
        ref_dict = {"low": 6, "high": 11}
        assert compare_to_range(6, ref_dict) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range(6.0, ref_dict) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range("6", ref_dict) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range(6, "06-11mm") == ComparisonResult.WITHIN_REPORTED_RANGE

    def test_boundary_equal_to_high(self):
        # Inclusive comparison: equal to high must be WITHIN_REPORTED_RANGE
        ref_dict = {"low": 6, "high": 11}
        assert compare_to_range(11, ref_dict) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range(11.0, ref_dict) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range("11", ref_dict) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range(11, "06-11mm") == ComparisonResult.WITHIN_REPORTED_RANGE

    def test_missing_reference_range(self):
        # None, empty dict, missing low or high
        assert compare_to_range(13, None) == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
        assert compare_to_range(13, {}) == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
        assert compare_to_range(13, {"low": 6}) == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
        assert compare_to_range(13, {"high": 11}) == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
        assert compare_to_range(13, "") == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED

    def test_numeric_types_supported(self):
        # int, float, string numeric
        assert compare_to_range(10, {"low": 5, "high": 15}) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range(10.5, {"low": 5.2, "high": 15.8}) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range("10.5", {"low": "5.2", "high": "15.8"}) == ComparisonResult.WITHIN_REPORTED_RANGE
        assert compare_to_range("60%", "55-74%") == ComparisonResult.WITHIN_REPORTED_RANGE

    def test_malformed_input_logs_warning_and_does_not_crash(self, caplog):
        # Non-numeric value
        with caplog.at_level(logging.WARNING):
            res_val = compare_to_range("not_a_number", {"low": 6, "high": 11})
            assert res_val == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
            assert any("non-numeric" in record.message.lower() for record in caplog.records)

        # Malformed bounds in dict
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            res_bounds = compare_to_range(10, {"low": "abc", "high": "xyz"})
            assert res_bounds == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
            assert any("bounds" in record.message.lower() for record in caplog.records)

        # Malformed unparseable string range
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            res_str = compare_to_range(10, "completely invalid range")
            assert res_str == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
            assert any("unparseable" in record.message.lower() for record in caplog.records)

    def test_parse_reference_bounds(self):
        low, high, unit = parse_reference_bounds("06-11mm")
        assert low == 6.0
        assert high == 11.0
        assert unit == "mm"

        low, high, unit = parse_reference_bounds("55-74%")
        assert low == 55.0
        assert high == 74.0
        assert unit == "%"

        low, high, unit = parse_reference_bounds({"low": 20, "high": 37, "unit": "mm"})
        assert low == 20.0
        assert high == 37.0
        assert unit == "mm"


# ===========================================================================
# 2. ALERTS TESTS
# ===========================================================================

class TestAlerts:
    """Unit tests for significance/alerts.py."""

    def test_static_alert_mappings(self):
        assert map_to_alert(SignificanceLevel.INFORMATIONAL) == AlertLevel.GREEN
        assert map_to_alert(SignificanceLevel.WITHIN_REPORTED_RANGE) == AlertLevel.GREEN
        assert map_to_alert(SignificanceLevel.NOTABLE_FINDING) == AlertLevel.YELLOW
        assert map_to_alert(SignificanceLevel.OUTSIDE_REPORTED_RANGE) == AlertLevel.ORANGE
        assert map_to_alert(SignificanceLevel.REQUIRES_CONTEXT) == AlertLevel.GREY
        assert map_to_alert(SignificanceLevel.UNRESOLVED) == AlertLevel.GREY
        assert map_to_alert(SignificanceLevel.CRITICAL) == AlertLevel.RED

    def test_all_significance_levels_covered(self):
        for sig in SignificanceLevel:
            alert = map_to_alert(sig)
            assert isinstance(alert, AlertLevel)
            assert alert in AlertLevel


# ===========================================================================
# 3. CLASSIFIER TESTS
# ===========================================================================

class TestClassifier:
    """Unit tests for significance/classifier.py."""

    def test_numeric_within_range(self):
        concept = {
            "concept": "Ejection Fraction",
            "type": "MEASUREMENT",
            "value": 60,
            "unit": "%",
            "reference_range": "55-74%",
            "assertion": "PRESENT",
        }
        res = classify_concept(concept)
        assert res.concept == "Ejection Fraction"
        assert res.comparison == ComparisonResult.WITHIN_REPORTED_RANGE
        assert res.significance == SignificanceLevel.WITHIN_REPORTED_RANGE
        assert res.alert_level == AlertLevel.GREEN
        assert "within the reported reference range" in res.basis
        assert "60 %" in res.basis or "60%" in res.basis

    def test_numeric_above_range(self):
        concept = {
            "concept": "Interventricular Septum Thickness in Diastole",
            "type": "MEASUREMENT",
            "value": 13,
            "unit": None,
            "reference_range": "06-11mm",
            "assertion": "PRESENT",
        }
        res = classify_concept(concept)
        assert res.concept == "Interventricular Septum Thickness in Diastole"
        assert res.comparison == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
        assert res.significance == SignificanceLevel.OUTSIDE_REPORTED_RANGE
        assert res.alert_level == AlertLevel.ORANGE
        assert res.basis == "Value 13 mm is above the reported reference range 6-11 mm"

    def test_numeric_below_range(self):
        concept = {
            "concept": "Fractional Shortening",
            "type": "MEASUREMENT",
            "value": 20,
            "unit": "%",
            "reference_range": "28-40%",
            "assertion": "PRESENT",
        }
        res = classify_concept(concept)
        assert res.comparison == ComparisonResult.BELOW_REPORTED_REFERENCE_RANGE
        assert res.significance == SignificanceLevel.OUTSIDE_REPORTED_RANGE
        assert res.alert_level == AlertLevel.ORANGE
        assert "is below the reported reference range" in res.basis

    def test_numeric_missing_range_requires_context(self):
        concept = {
            "concept": "Pulmonary Artery Systolic Pressure",
            "type": "MEASUREMENT",
            "value": 34,
            "unit": "mmHg",
            "reference_range": None,
            "assertion": "PRESENT",
        }
        res = classify_concept(concept)
        assert res.comparison == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
        assert res.significance == SignificanceLevel.REQUIRES_CONTEXT
        assert res.alert_level == AlertLevel.GREY
        assert "reported without a reference range" in res.basis

    def test_finding_assertion_normal(self):
        concept = {
            "concept": "Normal Right Ventricular Function",
            "type": "FINDING",
            "value": None,
            "assertion": "NORMAL",
        }
        res = classify_concept(concept)
        assert res.significance == SignificanceLevel.INFORMATIONAL
        assert res.alert_level == AlertLevel.GREEN
        assert res.basis == "Finding reported as normal"

    def test_finding_assertion_absent(self):
        concept = {
            "concept": "Regional Wall Motion Abnormality",
            "type": "FINDING",
            "value": None,
            "assertion": "ABSENT",
        }
        res = classify_concept(concept)
        assert res.significance == SignificanceLevel.INFORMATIONAL
        assert res.alert_level == AlertLevel.GREEN
        assert res.basis == "Finding reported as absent"

    def test_finding_assertion_present_notable(self):
        concept = {
            "concept": "Tricuspid Regurgitation",
            "type": "FINDING",
            "value": None,
            "assertion": "PRESENT",
            "modifiers": {"severity_text": "Mild"},
        }
        res = classify_concept(concept)
        assert res.significance == SignificanceLevel.NOTABLE_FINDING
        assert res.alert_level == AlertLevel.YELLOW
        assert "reported as present" in res.basis
        assert "Mild" in res.basis

    def test_finding_assertion_unresolved(self):
        concept_possible = {
            "concept": "Aortic Plaque",
            "type": "FINDING",
            "assertion": "POSSIBLE",
        }
        res_pos = classify_concept(concept_possible)
        assert res_pos.significance == SignificanceLevel.UNRESOLVED
        assert res_pos.alert_level == AlertLevel.GREY

        concept_unknown = {
            "concept": "Unknown Infiltrate",
            "type": "FINDING",
            "assertion": "UNKNOWN",
        }
        res_unk = classify_concept(concept_unknown)
        assert res_unk.significance == SignificanceLevel.UNRESOLVED
        assert res_unk.alert_level == AlertLevel.GREY

    def test_critical_never_auto_assigned(self):
        # Assert CRITICAL_OVERRIDES is an empty dict in this initial pass
        assert CRITICAL_OVERRIDES == {}
        # Test a severe-sounding concept to ensure it does NOT become CRITICAL
        concept = {
            "concept": "Severe Cardiac Finding",
            "type": "FINDING",
            "assertion": "PRESENT",
        }
        res = classify_concept(concept)
        assert res.significance != SignificanceLevel.CRITICAL
        assert res.alert_level != AlertLevel.RED

    def test_assertion_map_is_module_level_constant(self):
        assert isinstance(ASSERTION_SIGNIFICANCE_MAP, dict)
        assert ASSERTION_SIGNIFICANCE_MAP["NORMAL"] == SignificanceLevel.INFORMATIONAL
        assert ASSERTION_SIGNIFICANCE_MAP["ABSENT"] == SignificanceLevel.INFORMATIONAL
        assert ASSERTION_SIGNIFICANCE_MAP["PRESENT"] == SignificanceLevel.NOTABLE_FINDING
        assert ASSERTION_SIGNIFICANCE_MAP["POSSIBLE"] == SignificanceLevel.UNRESOLVED
        assert ASSERTION_SIGNIFICANCE_MAP["UNKNOWN"] == SignificanceLevel.UNRESOLVED

    def test_to_dict_serialization(self):
        concept = {
            "concept": "Ejection Fraction",
            "type": "MEASUREMENT",
            "value": 60,
            "unit": "%",
            "reference_range": "55-74%",
            "assertion": "PRESENT",
        }
        res = classify_concept(concept)
        d = res.to_dict()
        assert d["concept"] == "Ejection Fraction"
        assert d["comparison"] == "WITHIN_REPORTED_RANGE"
        assert d["significance"] == "WITHIN_REPORTED_RANGE"
        assert d["alert_level"] == "GREEN"
        assert isinstance(d["basis"], str)


# ===========================================================================
# 4. REAL REPORT VALIDATION
# ===========================================================================

def test_real_report_all_concepts_evaluated():
    """
    Evaluate every concept from output/sample_report/normalized/report.json.
    Assert no exceptions are raised, and every concept gets a non-null SignificanceResult.
    """
    assert REPORT_JSON_PATH.exists(), f"Missing report.json at {REPORT_JSON_PATH}"

    with open(REPORT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    concepts = data.get("clinical_information", {}).get("structured_clinical_concepts", [])
    assert len(concepts) > 0, "No structured_clinical_concepts found in report.json"

    results: list[SignificanceResult] = []
    for concept in concepts:
        res = classify_concept(concept)
        assert res is not None, f"classify_concept returned None for {concept}"
        assert isinstance(res, SignificanceResult)
        assert res.concept is not None and len(res.concept) > 0
        assert isinstance(res.comparison, ComparisonResult)
        assert isinstance(res.significance, SignificanceLevel)
        assert isinstance(res.alert_level, AlertLevel)
        assert isinstance(res.basis, str) and len(res.basis) > 0
        # Critical should never be auto-assigned
        assert res.significance != SignificanceLevel.CRITICAL
        assert res.alert_level != AlertLevel.RED
        results.append(res)

    assert len(results) == len(concepts)

    # Spot-check specific clinical landmarks in the sample echocardiogram:
    res_by_concept = {r.concept: r for r in results}

    # 1. Interventricular Septum (13 mm with ref 06-11mm) -> OUTSIDE_REPORTED_RANGE, ORANGE
    ivs = res_by_concept.get("Interventricular Septum Thickness in Diastole")
    assert ivs is not None
    assert ivs.comparison == ComparisonResult.ABOVE_REPORTED_REFERENCE_RANGE
    assert ivs.significance == SignificanceLevel.OUTSIDE_REPORTED_RANGE
    assert ivs.alert_level == AlertLevel.ORANGE
    assert ivs.basis == "Value 13 mm is above the reported reference range 6-11 mm"

    # 2. Ejection Fraction (60% with ref 55-74%) -> WITHIN_REPORTED_RANGE, GREEN
    ef = res_by_concept.get("Ejection Fraction")
    assert ef is not None
    assert ef.comparison == ComparisonResult.WITHIN_REPORTED_RANGE
    assert ef.significance == SignificanceLevel.WITHIN_REPORTED_RANGE
    assert ef.alert_level == AlertLevel.GREEN

    # 3. Fractional Shortening (32.5% with ref 28-40%) -> WITHIN_REPORTED_RANGE, GREEN
    fs = res_by_concept.get("Fractional Shortening")
    assert fs is not None
    assert fs.comparison == ComparisonResult.WITHIN_REPORTED_RANGE
    assert fs.significance == SignificanceLevel.WITHIN_REPORTED_RANGE
    assert fs.alert_level == AlertLevel.GREEN

    # 4. Regional Wall Motion Abnormality (ABSENT) -> INFORMATIONAL, GREEN
    rwma = res_by_concept.get("Regional Wall Motion Abnormality")
    assert rwma is not None
    assert rwma.significance == SignificanceLevel.INFORMATIONAL
    assert rwma.alert_level == AlertLevel.GREEN

    # 5. Tricuspid Regurgitation (PRESENT, Mild) -> NOTABLE_FINDING, YELLOW
    tr = res_by_concept.get("Mild Tricuspid Regurgitation") or res_by_concept.get("Tricuspid Regurgitation")
    assert tr is not None
    assert tr.significance == SignificanceLevel.NOTABLE_FINDING
    assert tr.alert_level == AlertLevel.YELLOW

    # 6. Pulmonary Artery Systolic Pressure (34 mmHg, no ref range) -> REQUIRES_CONTEXT, GREY
    pasp = res_by_concept.get("Pulmonary Artery Systolic Pressure")
    assert pasp is not None
    assert pasp.comparison == ComparisonResult.NO_REFERENCE_RANGE_SUPPLIED
    assert pasp.significance == SignificanceLevel.REQUIRES_CONTEXT
    assert pasp.alert_level == AlertLevel.GREY
