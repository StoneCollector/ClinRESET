"""
tests/test_validator.py

Tests for the extraction validator.
"""

from __future__ import annotations

import pytest

from extraction.validator import validate_extraction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


GOOD_TEXT = """\
ECHO CARDIOGRAPHY REPORT

M-MODE PARAMETERS

| MEASUREMENTS | VALUE | NORMAL VALUES |
|---|---|---|
| Ejection Fraction | 60 % | 55-74% |
| Fractional shortening | 32.5% | 28-40% |
| Aortic root diameter | 23 | 20-37mm |

FINAL IMPRESSION:

Normal LV function. EF 60%.
"""

GARBAGE_TEXT = "\x00\x01\x02\x03" * 50 + "abc"

VERY_SHORT_TEXT = "hi"

SPARSE_TEXT = "A" * 5 + "\n" * 100  # mostly blank lines


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_good_text_returns_good():
    status, warnings, scores = validate_extraction(GOOD_TEXT)
    assert status == "GOOD"
    assert scores["non_empty"] == 1.0
    assert scores["garbage_ratio"] == 1.0


def test_empty_string_returns_failed():
    status, warnings, scores = validate_extraction("")
    assert status == "FAILED"


def test_very_short_text_returns_failed():
    status, warnings, scores = validate_extraction(VERY_SHORT_TEXT)
    assert status == "FAILED"


def test_garbage_text_returns_failed():
    status, warnings, scores = validate_extraction(GARBAGE_TEXT)
    assert status == "FAILED"


def test_table_coherence_check_passes_for_valid_markdown():
    status, warnings, scores = validate_extraction(GOOD_TEXT)
    assert scores["table_coherence"] >= 0.9


def test_table_coherence_check_detects_broken_table():
    broken = """\
This is a report with some content and numbers like 60% and 32.5%
and also mentions measurements and findings and clinical notes.

| Col1 | Col2 | Col3 |
| a | b | c |
| x |
| p | q | r |
| m | n | o |
"""
    status, warnings, scores = validate_extraction(broken)
    # Should NOT be GOOD due to broken table row.
    assert scores["table_coherence"] < 1.0


def test_text_without_headings_is_not_hard_failed():
    # A lab result may lack formal headings — this should not be a hard failure.
    no_headings = (
        "Haemoglobin 13.5 g/dL normal range 12-16\n"
        "WBC 7.2 normal range 4-11\n"
        "Platelet 250 normal range 150-400\n"
        "Glucose 95 mg/dL fasting normal\n"
        "Creatinine 0.9 mg/dL normal\n"
    )
    status, warnings, scores = validate_extraction(no_headings)
    # Must not hard-fail just because there are no headings.
    assert status in ("GOOD", "DEGRADED")


def test_measurement_plausibility_scores_high_for_numeric_content():
    text = "Ejection Fraction 60% (55-74%) Fractional shortening 32.5% (28-40%)"
    _, _, scores = validate_extraction(text)
    assert scores["measurement_plausibility"] == 1.0


def test_validate_returns_three_values():
    status, warnings, scores = validate_extraction(GOOD_TEXT)
    assert isinstance(status, str)
    assert isinstance(warnings, list)
    assert isinstance(scores, dict)
    assert "_aggregate" in scores


def test_status_values_are_valid():
    for text in [GOOD_TEXT, VERY_SHORT_TEXT, GARBAGE_TEXT]:
        status, _, _ = validate_extraction(text)
        assert status in ("GOOD", "DEGRADED", "FAILED")
