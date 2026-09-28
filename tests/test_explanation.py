"""
Unit tests for ClinRESET Clinical Explanation Layer (Phase 7).
Verifies strict numerical cross-checking, zero discrepancy enforcement,
and deterministic template generation.
"""

import pytest
from src.explanation.models import (
    ConceptExplanation,
    ExplanationSection,
    ReportExplanation,
    VerificationResult,
)
from src.explanation.verifier import NumericalCrossChecker
from src.explanation.templates import DeterministicTemplateExplainer
from src.explanation.llm_explainer import GroundedLLMExplainer
from src.explanation.engine import ClinicalExplainer


def test_numerical_cross_checker_valid():
    source_facts = [
        {"concept": "IVSd", "value": 13, "unit": "mm", "reference_range": "06-11mm"},
        {"concept": "Blood Pressure", "value": 118, "unit": "mmHg", "original_text": "118/76 mmHg"},
        {"concept": "Liver size", "value": 15.8, "unit": "cm"},
    ]

    # Valid text containing only authorized numbers: 15.8, 13, 6, 11
    generated_text = (
        "Your liver measured 15.8 cm. "
        "The interventricular septum was measured at 13 mm, while the standard range is 6 to 11 mm."
    )

    result = NumericalCrossChecker.verify(generated_text, source_facts)
    assert result.is_valid is True
    assert len(result.discrepancies) == 0


def test_numerical_cross_checker_detects_hallucinations():
    source_facts = [
        {"concept": "IVSd", "value": 13, "unit": "mm", "reference_range": "06-11mm"},
        {"concept": "Liver size", "value": 15.8, "unit": "cm"},
    ]

    # Hallucinated text introduces numbers 25.5 and 99.0 not in source facts!
    hallucinated_text = (
        "Your liver is enlarged at 25.5 cm with an ejection fraction of 99.0 percent."
    )

    result = NumericalCrossChecker.verify(hallucinated_text, source_facts)
    assert result.is_valid is False
    assert 25.5 in result.discrepancies
    assert 99.0 in result.discrepancies
    assert "Numerical discrepancy detected" in result.reason


def test_deterministic_template_explainer_findings():
    # 1. Quantitative item
    item_quant = {
        "concept": "IVSd",
        "preferred_term": "Interventricular Septum",
        "layman_synonym": "Heart wall divider",
        "value": 13,
        "unit": "mm",
        "reference_range": "06-11mm",
        "alert_level": "ORANGE",
    }
    exp_quant = DeterministicTemplateExplainer.explain_finding(item_quant)
    assert "Heart wall divider" in exp_quant.explanation_text
    assert "13.0 mm" in exp_quant.explanation_text or "13 mm" in exp_quant.explanation_text
    assert "outside the standard reference range" in exp_quant.explanation_text

    # 2. Qualitative normal item
    item_norm = {
        "concept": "Lung fields",
        "preferred_term": "Lung fields",
        "assertion": "NORMAL",
        "alert_level": "GREEN",
    }
    exp_norm = DeterministicTemplateExplainer.explain_finding(item_norm)
    assert "found to be normal" in exp_norm.explanation_text

    # 3. Qualitative absent item
    item_absent = {
        "concept": "Pneumothorax",
        "preferred_term": "Pneumothorax",
        "layman_synonym": "Collapsed lung",
        "assertion": "ABSENT",
        "alert_level": "GREEN",
    }
    exp_absent = DeterministicTemplateExplainer.explain_finding(item_absent)
    assert "no sign or evidence of Pneumothorax (Collapsed lung)" in exp_absent.explanation_text


def test_deterministic_template_report_explanation():
    findings = [
        {
            "concept": "IVSd",
            "preferred_term": "Interventricular Septum",
            "layman_synonym": "Heart wall divider",
            "value": 13,
            "unit": "mm",
            "reference_range": "06-11mm",
            "alert_level": "ORANGE",
        },
        {
            "concept": "Pneumothorax",
            "preferred_term": "Pneumothorax",
            "layman_synonym": "Collapsed lung",
            "assertion": "ABSENT",
            "alert_level": "GREEN",
        },
        {
            "concept": "Disc bulge",
            "preferred_term": "Bulging spinal disc",
            "assertion": "PRESENT",
            "alert_level": "YELLOW",
        },
    ]

    report_exp = DeterministicTemplateExplainer.explain_report(findings, report_type="ultrasound")

    assert report_exp.generation_mode == "deterministic_template"
    assert report_exp.verification.is_valid is True
    assert len(report_exp.sections) >= 2
    assert len(report_exp.questions_for_doctor) == 3

    # Check key findings section exists
    titles = [s.title for s in report_exp.sections]
    assert "Key Findings to Discuss" in titles
    assert "Normal & Reassuring Observations" in titles


def test_clinical_explainer_facade():
    findings = [
        {"concept": "Liver", "preferred_term": "Liver", "value": 15.8, "unit": "cm", "alert_level": "ORANGE"},
        {"concept": "Calculus", "preferred_term": "Calculus", "assertion": "ABSENT", "alert_level": "GREEN"},
    ]

    exp = ClinicalExplainer.explain_report(findings, report_type="ct scans", use_llm=False)
    assert isinstance(exp, ReportExplanation)
    assert exp.verification.is_valid is True
    assert "reviewed" in exp.patient_summary
