#!/usr/bin/env python
"""
ClinRESET Gold Set Benchmark Evaluation CLI.
Usage:
  python evaluate.py --self-test
  python evaluate.py --predictions path/to/predictions.json
"""

import argparse
import json
import os
import sys

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.evaluation.scorer import EvaluationScorer


def run_self_test(scorer: EvaluationScorer):
    """
    Self-test runs the scorer using the gold set itself as predictions to verify
    the scoring harness produces 100% metrics across all modalities.
    """
    print("Running evaluation harness self-test (Gold vs Gold benchmark validation)...")
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
    table = scorer.format_score_table(result)
    print(table)

    # Validate invariants
    assert result.overall.f1 == 1.0, f"Expected 1.0 F1 in self-test, got {result.overall.f1}"
    assert result.overall.assertion_accuracy == 1.0, f"Expected 1.0 Assertion Accuracy, got {result.overall.assertion_accuracy}"
    assert result.overall.measurement_accuracy == 1.0, f"Expected 1.0 Measurement Accuracy, got {result.overall.measurement_accuracy}"
    print("[OK] Self-test passed: Evaluation harness and metric calculations verified!\n")


def run_evaluation(scorer: EvaluationScorer, predictions_path: str):
    if not os.path.exists(predictions_path):
        print(f"Error: Predictions file not found: {predictions_path}")
        sys.exit(1)

    with open(predictions_path, "r", encoding="utf-8") as f:
        preds = json.load(f)

    # If predictions are keyed by report_id or wrapped in a dict
    if "predictions" in preds:
        preds = preds["predictions"]

    result = scorer.score_predictions(preds)
    table = scorer.format_score_table(result)
    print(table)


def main():
    parser = argparse.ArgumentParser(description="Evaluate clinical extraction predictions against gold set.")
    parser.add_argument("--gold-set", type=str, default=None, help="Path to gold_set.json")
    parser.add_argument("--predictions", type=str, default=None, help="Path to predictions JSON")
    parser.add_argument("--self-test", action="store_true", help="Run self-test on gold set")

    args = parser.parse_args()

    scorer = EvaluationScorer(args.gold_set)

    if args.self_test or args.predictions is None:
        run_self_test(scorer)

    if args.predictions:
        run_evaluation(scorer, args.predictions)


if __name__ == "__main__":
    main()
