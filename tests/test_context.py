"""
tests/test_context.py

Unit and integration tests for report-level relationship grouping (significance/context.py).

Covers:
- Fully matching synthetic concept lists
- Partial concept lists with only 1 matching concept (rule must NOT fire)
- Empty concept and result lists (returns [])
- Integration test on real report.json output, printing matched groups for review.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from significance import (
    RELATIONSHIP_RULES,
    RelationshipType,
    SignificanceResult,
    classify_concept,
    find_context,
)

REPORT_JSON_PATH = Path("output") / "sample_report" / "normalized" / "report.json"


def test_synthetic_fully_matching_rule():
    """Rule matches fully when at least 2 concepts are present."""
    synthetic_concepts = [
        {"concept": "Concentric Left Ventricular Hypertrophy"},
        {"concept": "Interventricular Septum Thickness in Diastole"},
        {"concept": "Grade 1 Left Ventricular Diastolic Dysfunction"},
    ]
    groups = find_context(synthetic_concepts)
    assert len(groups) >= 1

    # Find the concentric LVH group
    lvh_group = next(
        (g for g in groups if "Concentric Left Ventricular Hypertrophy" in g["concepts"]),
        None,
    )
    assert lvh_group is not None
    assert len(lvh_group["concepts"]) == 3
    assert lvh_group["relationship"] == RelationshipType.RELATED_FINDINGS
    assert "commonly co-occur" in lvh_group["explanation"]
    assert "does not establish that one caused another" in lvh_group["explanation"]


def test_partial_match_only_one_concept_does_not_fire():
    """A rule with only 1 matching concept present must NOT fire."""
    # Only 1 concept from the concentric_lvh_cluster rule
    synthetic_concepts = [
        {"concept": "Concentric Left Ventricular Hypertrophy"},
        {"concept": "Completely Unrelated Finding"},
    ]
    groups = find_context(synthetic_concepts)
    assert groups == []


def test_empty_concepts_returns_empty_list():
    """find_context must return [] and never raise when input is empty or None."""
    assert find_context([]) == []
    assert find_context(None, None) == []
    assert find_context(concepts=[], results=[]) == []


def test_real_report_context_integration():
    """
    Run find_context against the actual sample_report report.json concepts.
    Assert at least one context group is produced and print output for manual review.
    """
    assert REPORT_JSON_PATH.exists(), f"Missing report.json at {REPORT_JSON_PATH}"

    with open(REPORT_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    concepts = data.get("clinical_information", {}).get("structured_clinical_concepts", [])
    assert len(concepts) > 0, "No structured_clinical_concepts found in report.json"

    results = [classify_concept(c) for c in concepts]
    groups = find_context(concepts, results)

    # Must produce at least one context group
    assert len(groups) >= 1, "Expected at least one context group from sample report"

    print("\n" + "=" * 60)
    print("PRODUCED CONTEXT GROUPS FOR MANUAL REVIEW:")
    print("=" * 60)
    for idx, g in enumerate(groups, 1):
        print(f"\nGroup {idx}:")
        print(f"  Matched Concepts: {g['concepts']}")
        print(f"  Relationship:     {g['relationship']}")
        print(f"  Explanation:      {g['explanation']}")
    print("=" * 60)

    # Verify structural integrity of all produced context groups
    for g in groups:
        assert isinstance(g["concepts"], list)
        assert len(g["concepts"]) >= 2
        assert g["relationship"] == RelationshipType.RELATED_FINDINGS
        assert isinstance(g["explanation"], str) and len(g["explanation"]) > 0
        # Ensure non-causal explanation wording
        assert "caused" in g["explanation"].lower() or "parallel" in g["explanation"].lower()
