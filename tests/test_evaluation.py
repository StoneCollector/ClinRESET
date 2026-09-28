import os
import pytest
from src.evaluation.scorer import EvaluationScorer


@pytest.fixture
def scorer():
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    gold_path = os.path.join(cur_dir, "..", "data", "gold_set", "gold_set.json")
    return EvaluationScorer(gold_path)


def test_gold_set_loaded(scorer):
    assert len(scorer.reports_by_id) == 28
    assert "echo_PA01" in scorer.reports_by_id
    assert "ct_PA01" in scorer.reports_by_id
    assert "general_sample4" in scorer.reports_by_id


def test_scorer_perfect_predictions(scorer):
    perfect_preds = {}
    for r_id, report in scorer.reports_by_id.items():
        perfect_preds[r_id] = [
            {
                "concept": f["concept"],
                "assertion": f["assertion"],
                "value": f.get("value"),
                "unit": f.get("unit"),
            }
            for f in report["facts"]
        ]

    result = scorer.score_predictions(perfect_preds)
    assert result.overall.f1 == 1.0
    assert result.overall.assertion_accuracy == 1.0
    assert result.overall.measurement_accuracy == 1.0
    assert result.overall.tp == 189
    assert result.overall.fp == 0
    assert result.overall.fn == 0


def test_scorer_imperfect_predictions(scorer):
    # Test partial recall and one wrong assertion
    sample_report = scorer.reports_by_id["echo_PA01"]
    facts = sample_report["facts"]

    imperfect_preds = {
        "echo_PA01": [
            # Fact 1: perfect
            {"concept": facts[0]["concept"], "assertion": facts[0]["assertion"], "value": facts[0]["value"], "unit": facts[0]["unit"]},
            # Fact 2: wrong assertion
            {"concept": facts[1]["concept"], "assertion": "PRESENT" if facts[1]["assertion"] == "ABSENT" else "ABSENT"},
            # Spurious hallucination
            {"concept": "random hallucinated finding", "assertion": "PRESENT"}
        ]
    }

    result = scorer.score_predictions(imperfect_preds)
    echo_metrics = result.by_modality["echocardiography"]

    assert echo_metrics.tp == 2
    assert echo_metrics.fp == 1  # 1 spurious
    assert echo_metrics.correct_assertions == 1  # 1 out of 2 correct
    assert echo_metrics.assertion_accuracy == 0.5
