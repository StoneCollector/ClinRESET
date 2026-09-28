"""
ClinRESET Extraction Evaluation Scorer.
Scores extracted clinical facts against the curated gold set.
Evaluates Concepts (P/R/F1), Assertions (Accuracy), Measurements (Value & Unit accuracy).
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class MetricSummary:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    correct_assertions: int = 0
    correct_measurements: int = 0
    total_expected_measurements: int = 0
    correct_units: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

    @property
    def assertion_accuracy(self) -> float:
        return (self.correct_assertions / self.tp) if self.tp > 0 else 0.0

    @property
    def measurement_accuracy(self) -> float:
        if self.total_expected_measurements == 0:
            return 1.0
        return self.correct_measurements / self.total_expected_measurements


@dataclass
class EvaluationResult:
    by_modality: Dict[str, MetricSummary] = field(default_factory=dict)
    overall: MetricSummary = field(default_factory=MetricSummary)
    total_reports: int = 0
    evaluated_reports: int = 0


class EvaluationScorer:
    def __init__(self, gold_set_path: Optional[str] = None):
        if gold_set_path is None:
            # Default to scratch/data/gold_set/gold_set.json
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            scratch_root = os.path.abspath(os.path.join(cur_dir, "..", ".."))
            gold_set_path = os.path.join(scratch_root, "data", "gold_set", "gold_set.json")

        self.gold_set_path = gold_set_path
        self.gold_data = self._load_gold_set(gold_set_path)
        self.reports_by_id = {r["report_id"]: r for r in self.gold_data.get("reports", [])}

    def _load_gold_set(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Gold set file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _normalize_tokens(text: str) -> set:
        """Tokenize and normalize text for loose concept matching."""
        text = text.lower()
        tokens = re.findall(r"\b[a-z0-9]+\b", text)
        stop_words = {"is", "the", "a", "an", "and", "in", "of", "with", "or", "to", "for", "on", "at"}
        return {t for t in tokens if t not in stop_words}

    def _concept_match(self, pred_concept: str, gold_concept: str) -> bool:
        """Matches concept using normalized token overlap or substring containment."""
        pred_norm = pred_concept.strip().lower()
        gold_norm = gold_concept.strip().lower()

        if pred_norm == gold_norm or pred_norm in gold_norm or gold_norm in pred_norm:
            return True

        pred_tokens = self._normalize_tokens(pred_norm)
        gold_tokens = self._normalize_tokens(gold_norm)

        if not pred_tokens or not gold_tokens:
            return False

        intersection = pred_tokens.intersection(gold_tokens)
        union = pred_tokens.union(gold_tokens)
        jaccard = len(intersection) / len(union) if union else 0.0

        # Substantial token overlap
        return jaccard >= 0.4 or len(intersection) >= min(len(pred_tokens), len(gold_tokens)) * 0.7

    @staticmethod
    def _measurement_match(pred_val: Optional[float], gold_val: Optional[float]) -> bool:
        if gold_val is None:
            return pred_val is None
        if pred_val is None:
            return False
        # Match within 5% tolerance or 0.1 absolute tolerance
        if abs(pred_val - gold_val) < 0.1001:
            return True
        if gold_val != 0:
            return abs(pred_val - gold_val) / abs(gold_val) <= 0.05
        return False

    @staticmethod
    def _unit_match(pred_unit: Optional[str], gold_unit: Optional[str]) -> bool:
        if gold_unit is None:
            return True  # If no unit expected, don't penalize
        if pred_unit is None:
            return False
        p = pred_unit.strip().lower().replace(" ", "")
        g = gold_unit.strip().lower().replace(" ", "")
        return p == g

    def score_predictions(self, predictions_by_report: Dict[str, List[Dict[str, Any]]]) -> EvaluationResult:
        """
        Score a dictionary of predictions:
        {
           "echo_PA01": [{"concept": "...", "assertion": "...", "value": 23.0, "unit": "mm"}, ...],
           ...
        }
        """
        result = EvaluationResult(total_reports=len(self.reports_by_id))
        modality_metrics: Dict[str, MetricSummary] = {}
        overall = MetricSummary()

        for report_id, gold_report in self.reports_by_id.items():
            modality = gold_report.get("modality", "unknown")
            if modality not in modality_metrics:
                modality_metrics[modality] = MetricSummary()

            mod_metric = modality_metrics[modality]
            gold_facts = gold_report.get("facts", [])
            pred_facts = predictions_by_report.get(report_id, [])

            if report_id in predictions_by_report:
                result.evaluated_reports += 1

            matched_gold_indices = set()
            matched_pred_indices = set()

            # Find TP matches
            for p_idx, pred in enumerate(pred_facts):
                pred_c = pred.get("concept", "")
                for g_idx, gold in enumerate(gold_facts):
                    if g_idx in matched_gold_indices:
                        continue
                    if self._concept_match(pred_c, gold.get("concept", "")):
                        matched_gold_indices.add(g_idx)
                        matched_pred_indices.add(p_idx)

                        # True positive concept
                        mod_metric.tp += 1
                        overall.tp += 1

                        # Assertion check
                        if pred.get("assertion", "").upper() == gold.get("assertion", "").upper():
                            mod_metric.correct_assertions += 1
                            overall.correct_assertions += 1

                        # Measurement check
                        gold_val = gold.get("value")
                        if gold_val is not None:
                            mod_metric.total_expected_measurements += 1
                            overall.total_expected_measurements += 1
                            if self._measurement_match(pred.get("value"), gold_val):
                                mod_metric.correct_measurements += 1
                                overall.correct_measurements += 1
                            if self._unit_match(pred.get("unit"), gold.get("unit")):
                                mod_metric.correct_units += 1
                                overall.correct_units += 1

                        break

            # False positives (predictions with no matching gold fact)
            fps = len(pred_facts) - len(matched_pred_indices)
            mod_metric.fp += fps
            overall.fp += fps

            # False negatives (gold facts not extracted)
            fns = len(gold_facts) - len(matched_gold_indices)
            mod_metric.fn += fns
            overall.fn += fns

            # Any expected measurements that were completely missed
            for g_idx, gold in enumerate(gold_facts):
                if g_idx not in matched_gold_indices and gold.get("value") is not None:
                    mod_metric.total_expected_measurements += 1
                    overall.total_expected_measurements += 1

        result.by_modality = modality_metrics
        result.overall = overall
        return result

    def format_score_table(self, result: EvaluationResult) -> str:
        """Formats the evaluation result into a standardized Markdown/ASCII table."""
        header = (
            f"| Modality            | Gold Facts | Pred TP | Pred FP | Pred FN | Concept Prec | Concept Rec | Concept F1 | Assert Acc | Meas Acc | Overall Score |\n"
            f"|---------------------|------------|---------|---------|---------|--------------|-------------|------------|------------|----------|---------------|"
        )

        rows = []
        for mod, m in sorted(result.by_modality.items()):
            total_gold = m.tp + m.fn
            overall_score = (m.f1 * 0.5) + (m.assertion_accuracy * 0.3) + (m.measurement_accuracy * 0.2)
            rows.append(
                f"| {mod:<19} | {total_gold:<10} | {m.tp:<7} | {m.fp:<7} | {m.fn:<7} | "
                f"{m.precision * 100:>11.1f}% | {m.recall * 100:>10.1f}% | {m.f1 * 100:>9.1f}% | "
                f"{m.assertion_accuracy * 100:>9.1f}% | {m.measurement_accuracy * 100:>7.1f}% | "
                f"{overall_score * 100:>12.1f}% |"
            )

        ov = result.overall
        total_gold_ov = ov.tp + ov.fn
        ov_score = (ov.f1 * 0.5) + (ov.assertion_accuracy * 0.3) + (ov.measurement_accuracy * 0.2)
        total_row = (
            f"| **OVERALL**         | **{total_gold_ov:<8}** | **{ov.tp:<5}** | **{ov.fp:<5}** | **{ov.fn:<5}** | "
            f"**{ov.precision * 100:>9.1f}%** | **{ov.recall * 100:>8.1f}%** | **{ov.f1 * 100:>7.1f}%** | "
            f"**{ov.assertion_accuracy * 100:>7.1f}%** | **{ov.measurement_accuracy * 100:>5.1f}%** | "
            f"**{ov_score * 100:>10.1f}%** |"
        )

        summary_info = (
            f"\n### ClinRESET Benchmark Evaluation Summary\n"
            f"- Total Gold Reports: {result.total_reports}\n"
            f"- Evaluated Reports: {result.evaluated_reports}\n"
            f"- Total Clinical Facts in Benchmark: {total_gold_ov}\n\n"
        )

        return summary_info + header + "\n" + "\n".join(rows) + "\n" + total_row + "\n"
