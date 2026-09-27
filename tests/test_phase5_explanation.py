"""
tests/test_phase5_explanation.py

Phase 5A: Deterministic Clinical Explanation Engine Test Suite.

Covers all 22 required test cases specified in the Phase 5A requirements:
 1. Ejection Fraction
 2. Fractional Shortening
 3. PASP
 4. Mild TR
 5. Grade 1 LVDD
 6. No RWMA
 7. No Aortic regurgitation
 8. No Pulmonary regurgitation
 9. No LA/LV clot
10. No effusion
11. Normal RV function
12. Conc LVH
13. Aortic velocity
14. Pulmonary velocity
15. Pulmonary Valve E-F Slope
16. Unknown concept
17. Ambiguous concept
18. Missing explanation entry
19. Provenance preservation
20. Value/unit preservation
21. Modifier preservation
22. No clinical interpretation leakage
Plus:
- Concept collision prevention ("Ejection Fraction" vs "Pulmonary Valve E-F Slope")
- Real report end-to-end acceptance testing
- Section categorization and markdown rendering
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from clinical_explanation import (
    ClinicalExplainer,
    ConceptExplanation,
    ExplanationSection,
    ExplanationStatus,
    ReportExplanations,
    UnavailabilityReason,
    format_explanations_as_markdown,
    generate_clinical_explanations,
    lookup_concept,
    organize_explanations_into_sections,
)
from extraction.pipeline import extract_document


SAMPLE_PDF = Path("txt_extractor") / "sample_report.pdf"

FORBIDDEN_WORDS = [
    "healthy",
    "unhealthy",
    "dangerous",
    "serious",
    "high risk",
    "low risk",
    "requires treatment",
    "needs medication",
    "consult a doctor",
    "prognosis",
    "heart failure",
    "pulmonary hypertension",
    "enlarged heart",
]


@pytest.fixture
def explainer() -> ClinicalExplainer:
    return ClinicalExplainer()


# ===========================================================================
# 1. Ejection Fraction
# ===========================================================================
def test_01_ejection_fraction(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Ejection Fraction",
        "type": "MEASUREMENT",
        "semantic_category": "FUNCTION",
        "value": 60,
        "unit": "%",
        "reference_range": "55-74%",
        "assertion": "PRESENT",
        "related_anatomy": ["Left Ventricle"],
        "provenance": {"source_text": "EF = 60%"},
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.concept == "Ejection Fraction"
    assert exp.value == 60
    assert exp.unit == "%"
    assert "left ventricle" in exp.explanation.lower()
    assert "60 %" in exp.explanation or "60%" in exp.explanation
    assert "reported reference range: 55-74%" in exp.explanation
    assert exp.related_anatomy == ["Left Ventricle"]


# ===========================================================================
# 2. Fractional Shortening
# ===========================================================================
def test_02_fractional_shortening(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Fractional Shortening",
        "type": "MEASUREMENT",
        "semantic_category": "FUNCTION",
        "value": 32.5,
        "unit": "%",
        "reference_range": "28-40%",
        "assertion": "PRESENT",
        "related_anatomy": ["Left Ventricle"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.concept == "Fractional Shortening"
    assert exp.value == 32.5
    assert exp.unit == "%"
    assert "left ventricle" in exp.explanation.lower()
    assert "32.5 %" in exp.explanation or "32.5%" in exp.explanation


# ===========================================================================
# 3. PASP (Pulmonary Artery Systolic Pressure)
# ===========================================================================
def test_03_pasp(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Pulmonary Artery Systolic Pressure",
        "type": "MEASUREMENT",
        "semantic_category": "PRESSURE",
        "value": 34,
        "unit": "mmHg",
        "assertion": "PRESENT",
        "related_anatomy": ["Pulmonary Artery"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.concept == "Pulmonary Artery Systolic Pressure"
    assert exp.value == 34
    assert exp.unit == "mmHg"
    assert "pulmonary artery" in exp.explanation.lower()
    assert "34 mmHg" in exp.explanation
    # Must NOT diagnose pulmonary hypertension
    assert "hypertension" not in exp.explanation.lower()


# ===========================================================================
# 4. Mild TR (Tricuspid Regurgitation)
# ===========================================================================
def test_04_mild_tr(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Tricuspid Regurgitation",
        "type": "FINDING",
        "semantic_category": "VALVULAR_FINDING",
        "assertion": "PRESENT",
        "modifiers": {"severity_text": "Mild"},
        "related_anatomy": ["Tricuspid Valve"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.concept == "Tricuspid Regurgitation"
    assert exp.modifiers["severity_text"] == "Mild"
    assert "mild tricuspid regurgitation" in exp.explanation.lower()
    assert "tricuspid valve" in exp.explanation.lower()
    # Must NOT interpret as dangerous or requiring treatment
    assert "treatment" not in exp.explanation.lower()


# ===========================================================================
# 5. Grade 1 LVDD (Left Ventricular Diastolic Dysfunction)
# ===========================================================================
def test_05_grade_1_lvdd(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Left Ventricular Diastolic Dysfunction",
        "type": "FINDING",
        "semantic_category": "DIASTOLIC_FUNCTION",
        "assertion": "PRESENT",
        "modifiers": {"grade_text": "Grade 1"},
        "related_anatomy": ["Left Ventricle"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.concept == "Left Ventricular Diastolic Dysfunction"
    assert exp.modifiers["grade_text"] == "Grade 1"
    assert "grade 1" in exp.explanation.lower()
    assert "filling" in exp.explanation.lower() or "relax" in exp.explanation.lower()
    # Must NOT decide disease severity or risk
    assert "serious" not in exp.explanation.lower()


# ===========================================================================
# 6. No RWMA (Regional Wall Motion Abnormality)
# ===========================================================================
def test_06_no_rwma(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Regional Wall Motion Abnormality",
        "type": "FINDING",
        "semantic_category": "WALL_MOTION",
        "assertion": "ABSENT",
        "related_anatomy": ["Heart Wall"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.assertion == "ABSENT"
    assert "none was reported" in exp.explanation.lower()
    assert "regional wall motion abnormality" in exp.explanation.lower()


# ===========================================================================
# 7. No Aortic Regurgitation
# ===========================================================================
def test_07_no_aortic_regurgitation(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Aortic Regurgitation",
        "type": "FINDING",
        "semantic_category": "VALVULAR_FINDING",
        "assertion": "ABSENT",
        "related_anatomy": ["Aortic Valve"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.assertion == "ABSENT"
    assert "none was reported" in exp.explanation.lower()
    assert "aortic valve" in exp.explanation.lower()
    assert "during diastole, when the heart relaxes and fills" in exp.explanation.lower()


# ===========================================================================
# 8. No Pulmonary Regurgitation
# ===========================================================================
def test_08_no_pulmonary_regurgitation(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Pulmonary Regurgitation",
        "type": "FINDING",
        "semantic_category": "VALVULAR_FINDING",
        "assertion": "ABSENT",
        "related_anatomy": ["Pulmonary Valve"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.assertion == "ABSENT"
    assert "none was reported" in exp.explanation.lower()
    assert "pulmonary" in exp.explanation.lower()


# ===========================================================================
# 9. No LA/LV Clot (Thrombus)
# ===========================================================================
def test_09_no_lalv_clot(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Thrombus",
        "type": "FINDING",
        "semantic_category": "THROMBUS",
        "assertion": "ABSENT",
        "related_anatomy": ["Left Atrium", "Left Ventricle"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.assertion == "ABSENT"
    assert "none was reported" in exp.explanation.lower()
    assert "clot" in exp.explanation.lower() or "thrombus" in exp.explanation.lower()


# ===========================================================================
# 10. No Effusion (Pericardial Effusion)
# ===========================================================================
def test_10_no_effusion(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Pericardial Effusion",
        "type": "FINDING",
        "semantic_category": "EFFUSION",
        "assertion": "ABSENT",
        "related_anatomy": ["Pericardium"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.assertion == "ABSENT"
    assert "none was reported" in exp.explanation.lower()
    assert "pericardial effusion" in exp.explanation.lower()


# ===========================================================================
# 11. Normal RV Function
# ===========================================================================
def test_11_normal_rv_function(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Right Ventricular Function",
        "type": "FINDING",
        "semantic_category": "FUNCTION",
        "assertion": "NORMAL",
        "related_anatomy": ["Right Ventricle"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.assertion == "NORMAL"
    assert "described as normal" in exp.explanation.lower()
    assert "right ventricle" in exp.explanation.lower()


# ===========================================================================
# 12. Conc LVH (Concentric Left Ventricular Hypertrophy)
# ===========================================================================
def test_12_conc_lvh(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Concentric Left Ventricular Hypertrophy",
        "type": "FINDING",
        "semantic_category": "STRUCTURAL_FINDING",
        "assertion": "PRESENT",
        "modifiers": {"pattern": "Concentric"},
        "related_anatomy": ["Left Ventricle"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.concept == "Concentric Left Ventricular Hypertrophy"
    assert "concentric" in exp.explanation.lower()
    assert "left ventricle" in exp.explanation.lower()
    # Must NOT call it enlarged heart or dangerous
    assert "enlarged heart" not in exp.explanation.lower()
    assert "dangerous" not in exp.explanation.lower()


# ===========================================================================
# 13. Aortic Velocity
# ===========================================================================
def test_13_aortic_velocity(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Aortic Velocity",
        "type": "MEASUREMENT",
        "semantic_category": "DOPPLER_MEASUREMENT",
        "value": 1.47,
        "unit": "m/s",
        "assertion": "PRESENT",
        "related_anatomy": ["Aorta"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.concept == "Aortic Velocity"
    assert exp.value == 1.47
    assert exp.unit == "m/s"
    assert "1.47 m/s" in exp.explanation
    assert "aortic" in exp.explanation.lower()


# ===========================================================================
# 14. Pulmonary Velocity
# ===========================================================================
def test_14_pulmonary_velocity(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Pulmonary Velocity",
        "type": "MEASUREMENT",
        "semantic_category": "DOPPLER_MEASUREMENT",
        "value": 1.0,
        "unit": "m/s",
        "assertion": "PRESENT",
        "related_anatomy": ["Pulmonary Artery"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert exp.concept == "Pulmonary Velocity"
    assert exp.value == 1.0
    assert exp.unit == "m/s"
    assert "1.0 m/s" in exp.explanation
    assert "pulmonary" in exp.explanation.lower()


# ===========================================================================
# 15. Pulmonary Valve E-F Slope
# ===========================================================================
def test_15_pulmonary_valve_ef_slope(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Normal Pulmonary Valve EF Slope",
        "type": "FINDING",
        "semantic_category": "DOPPLER_MEASUREMENT",
        "assertion": "NORMAL",
        "related_anatomy": ["Pulmonary Valve"],
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLAINED
    assert "e-f slope" in exp.explanation.lower()
    assert "pulmonary valve" in exp.explanation.lower()
    # Must NOT mention ejection fraction
    assert "ejection fraction" not in exp.explanation.lower()


# ===========================================================================
# 16. Unknown Concept Handling
# ===========================================================================
def test_16_unknown_concept(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Unknown Novel Cardiac Biomarker X",
        "original_text": "UNKN_X",
        "type": "FINDING",
        "semantic_category": "OTHER_CLINICAL",
        "assertion": "PRESENT",
        "provenance": {"ambiguity_status": "UNKNOWN"},
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLANATION_UNAVAILABLE
    assert exp.unavailability_reason == UnavailabilityReason.UNKNOWN_CONCEPT
    assert "unavailable" in exp.explanation.lower()


# ===========================================================================
# 17. Ambiguous Concept Handling
# ===========================================================================
def test_17_ambiguous_concept(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "RA",
        "original_text": "RA",
        "type": "FINDING",
        "semantic_category": "OTHER_CLINICAL",
        "assertion": "PRESENT",
        "provenance": {
            "ambiguity_status": "AMBIGUOUS",
            "ambiguity": True,
            "candidates": ["Right Atrium", "Rheumatoid Arthritis"],
        },
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLANATION_UNAVAILABLE
    assert exp.unavailability_reason == UnavailabilityReason.AMBIGUOUS_CONCEPT
    assert "ambiguous" in exp.explanation.lower()


# ===========================================================================
# 18. Missing Explanation Entry
# ===========================================================================
def test_18_missing_explanation_entry(explainer: ClinicalExplainer):
    concept_data = {
        "concept": "Unregistered Fictional Clinical Concept 404",
        "original_text": "UFCC 404",
        "type": "FINDING",
        "semantic_category": "OTHER_CLINICAL",
        "assertion": "PRESENT",
        "provenance": {"ambiguity_status": "RESOLVED"},
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.status == ExplanationStatus.EXPLANATION_UNAVAILABLE
    assert exp.unavailability_reason == UnavailabilityReason.NOT_IN_KNOWLEDGE_BASE
    assert "knowledge base" in exp.explanation.lower()


# ===========================================================================
# 19. Provenance Preservation
# ===========================================================================
def test_19_provenance_preservation(explainer: ClinicalExplainer):
    prov = {
        "page": 1,
        "source_section": "FINDINGS",
        "source_text": "EF 60%",
        "normalization_source": "CORPUS",
    }
    concept_data = {
        "concept": "Ejection Fraction",
        "type": "MEASUREMENT",
        "semantic_category": "FUNCTION",
        "value": 60,
        "unit": "%",
        "assertion": "PRESENT",
        "provenance": prov,
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.provenance == prov
    assert exp.provenance["page"] == 1
    assert exp.provenance["source_section"] == "FINDINGS"
    assert exp.provenance["source_text"] == "EF 60%"
    assert exp.provenance["normalization_source"] == "CORPUS"


# ===========================================================================
# 20. Value and Unit Preservation
# ===========================================================================
def test_20_value_unit_preservation(explainer: ClinicalExplainer):
    test_values = [
        (60, "%", "55-74%"),
        (32.5, "%", "28-40%"),
        (34, "mmHg", None),
        (1.47, "m/s", None),
        (1.0, "m/s", None),
        (30, "mm", "20-37 mm"),
    ]
    for val, u, rng in test_values:
        concept_data = {
            "concept": "Aortic Root Diameter" if u == "mm" else "Ejection Fraction",
            "type": "MEASUREMENT",
            "semantic_category": "MEASUREMENT",
            "value": val,
            "unit": u,
            "reference_range": rng,
            "assertion": "PRESENT",
        }
        exp = explainer.explain_concept(concept_data)
        assert exp.value == val
        assert exp.unit == u
        assert exp.reference_range == rng
        assert f"{val}" in exp.explanation
        if u:
            assert u in exp.explanation
        if rng:
            assert rng in exp.explanation


# ===========================================================================
# 21. Modifier Preservation
# ===========================================================================
def test_21_modifier_preservation(explainer: ClinicalExplainer):
    modifiers = {
        "severity_text": "Mild",
        "grade_text": "Grade 1",
        "pattern": "Concentric",
    }
    concept_data = {
        "concept": "Tricuspid Regurgitation",
        "type": "FINDING",
        "semantic_category": "VALVULAR_FINDING",
        "assertion": "PRESENT",
        "modifiers": modifiers,
    }
    exp = explainer.explain_concept(concept_data)
    assert exp.modifiers == modifiers
    assert "concentric" in exp.explanation.lower()
    assert "grade 1" in exp.explanation.lower()
    assert "mild" in exp.explanation.lower()


# ===========================================================================
# 22. No Clinical Interpretation Leakage
# ===========================================================================
def test_22_no_clinical_interpretation_leakage(explainer: ClinicalExplainer):
    concepts_to_test = [
        {"concept": "Ejection Fraction", "type": "MEASUREMENT", "value": 60, "unit": "%", "assertion": "PRESENT"},
        {"concept": "Fractional Shortening", "type": "MEASUREMENT", "value": 32.5, "unit": "%", "assertion": "PRESENT"},
        {"concept": "Pulmonary Artery Systolic Pressure", "type": "MEASUREMENT", "value": 34, "unit": "mmHg", "assertion": "PRESENT"},
        {"concept": "Tricuspid Regurgitation", "type": "FINDING", "modifiers": {"severity_text": "Mild"}, "assertion": "PRESENT"},
        {"concept": "Left Ventricular Diastolic Dysfunction", "type": "FINDING", "modifiers": {"grade_text": "Grade 1"}, "assertion": "PRESENT"},
        {"concept": "Regional Wall Motion Abnormality", "type": "FINDING", "assertion": "ABSENT"},
        {"concept": "Aortic Regurgitation", "type": "FINDING", "assertion": "ABSENT"},
        {"concept": "Pulmonary Regurgitation", "type": "FINDING", "assertion": "ABSENT"},
        {"concept": "Thrombus", "type": "FINDING", "assertion": "ABSENT"},
        {"concept": "Pericardial Effusion", "type": "FINDING", "assertion": "ABSENT"},
        {"concept": "Right Ventricular Function", "type": "FINDING", "assertion": "NORMAL"},
        {"concept": "Concentric Left Ventricular Hypertrophy", "type": "FINDING", "assertion": "PRESENT"},
        {"concept": "Aortic Velocity", "type": "MEASUREMENT", "value": 1.47, "unit": "m/s", "assertion": "PRESENT"},
        {"concept": "Pulmonary Velocity", "type": "MEASUREMENT", "value": 1.0, "unit": "m/s", "assertion": "PRESENT"},
        {"concept": "Normal Pulmonary Valve EF Slope", "type": "FINDING", "assertion": "NORMAL"},
    ]
    for c in concepts_to_test:
        exp = explainer.explain_concept(c)
        assert exp.status == ExplanationStatus.EXPLAINED
        text_lower = exp.explanation.lower()
        for forbidden in FORBIDDEN_WORDS:
            assert forbidden not in text_lower, (
                f"Forbidden clinical judgment word '{forbidden}' found in explanation for '{c['concept']}': {exp.explanation}"
            )


# ===========================================================================
# 23. Collision Prevention: Ejection Fraction vs Pulmonary Valve EF Slope
# ===========================================================================
def test_collision_prevention_ef_vs_ef_slope(explainer: ClinicalExplainer):
    ef_concept = {
        "concept": "Ejection Fraction",
        "type": "MEASUREMENT",
        "semantic_category": "FUNCTION",
        "value": 60,
        "unit": "%",
        "assertion": "PRESENT",
        "related_anatomy": ["Left Ventricle"],
    }
    slope_concept = {
        "concept": "Normal Pulmonary Valve EF Slope",
        "type": "FINDING",
        "semantic_category": "DOPPLER_MEASUREMENT",
        "assertion": "NORMAL",
        "related_anatomy": ["Pulmonary Valve"],
    }

    ef_exp = explainer.explain_concept(ef_concept)
    slope_exp = explainer.explain_concept(slope_concept)

    # 1. Names and identities are distinct
    assert ef_exp.concept != slope_exp.concept
    assert ef_exp.concept == "Ejection Fraction"
    assert "Pulmonary Valve" in slope_exp.concept

    # 2. Anatomies are distinct
    assert ef_exp.related_anatomy == ["Left Ventricle"]
    assert slope_exp.related_anatomy == ["Pulmonary Valve"]

    # 3. Content does not cross-pollinate
    assert "left ventricle" in ef_exp.explanation.lower()
    assert "pulmonary valve" in slope_exp.explanation.lower()
    assert "ejection fraction" not in slope_exp.explanation.lower()
    assert "e-f slope" not in ef_exp.explanation.lower()


# ===========================================================================
# 24. Report Deduplication Logic
# ===========================================================================
def test_explanation_deduplication(explainer: ClinicalExplainer):
    duplicate_concepts = [
        {
            "concept": "Ejection Fraction",
            "type": "MEASUREMENT",
            "value": 60,
            "unit": "%",
            "assertion": "PRESENT",
            "provenance": {"source_section": "MEASUREMENTS"},
        },
        {
            "concept": "Ejection Fraction",
            "type": "MEASUREMENT",
            "value": 60,
            "unit": "%",
            "assertion": "PRESENT",
            "provenance": {"source_section": "FINAL IMPRESSION"},
        },
    ]
    explanations = explainer.explain_report_concepts(duplicate_concepts)
    assert len(explanations) == 1
    assert explanations[0].concept == "Ejection Fraction"


# ===========================================================================
# 25. Section Categorization & Markdown Renderer
# ===========================================================================
def test_sections_and_markdown_renderer(explainer: ClinicalExplainer):
    concepts = [
        {"concept": "Ejection Fraction", "type": "MEASUREMENT", "semantic_category": "FUNCTION", "value": 60, "unit": "%"},
        {"concept": "Interatrial Septum", "type": "FINDING", "semantic_category": "STRUCTURAL_FINDING", "assertion": "NORMAL"},
        {"concept": "Aortic Root Diameter", "type": "MEASUREMENT", "semantic_category": "MEASUREMENT", "value": 30, "unit": "mm"},
        {"concept": "Regional Wall Motion Abnormality", "type": "FINDING", "semantic_category": "WALL_MOTION", "assertion": "ABSENT"},
        {"concept": "Left Ventricular Diastolic Dysfunction", "type": "FINDING", "semantic_category": "DIASTOLIC_FUNCTION", "assertion": "PRESENT"},
        {"concept": "Tricuspid Regurgitation", "type": "FINDING", "semantic_category": "VALVULAR_FINDING", "assertion": "PRESENT"},
        {"concept": "Pulmonary Artery Systolic Pressure", "type": "MEASUREMENT", "semantic_category": "PRESSURE", "value": 34, "unit": "mmHg"},
        {"concept": "Pericardial Effusion", "type": "FINDING", "semantic_category": "EFFUSION", "assertion": "ABSENT"},
    ]
    exps = [explainer.explain_concept(c) for c in concepts]
    sections = organize_explanations_into_sections(exps)
    section_titles = [s.title for s in sections]

    assert "Heart Function" in section_titles
    assert "Heart Structure" in section_titles
    assert "Heart Dimensions & Thickness" in section_titles
    assert "Wall Motion" in section_titles
    assert "Diastolic Function" in section_titles
    assert "Valvular Findings" in section_titles
    assert "Pressure and Doppler" in section_titles
    assert "Other Findings" in section_titles

    report_exp = ReportExplanations(explanations=exps, sections=sections)
    md = format_explanations_as_markdown(report_exp)
    assert "# Clinical Report Explanations (Phase 5A)" in md
    assert "## Heart Function" in md
    assert "**Ejection Fraction** (60 %)" in md


# ===========================================================================
# 26. Real Echo Report End-to-End Acceptance Test
# ===========================================================================
def test_real_echo_report_end_to_end():
    assert SAMPLE_PDF.exists(), f"Sample PDF missing: {SAMPLE_PDF}"
    result = extract_document(SAMPLE_PDF, save_output=False)
    ci = result.clinical_information
    assert ci is not None, "ClinicalInformation was not generated"

    report_dict = result.to_dict()
    ci_dict = report_dict.get("clinical_information", {})

    # Verify output contract presence
    assert "structured_clinical_concepts" in ci_dict
    assert "explanations" in ci_dict
    assert "explanation_sections" in ci_dict

    explanations = ci_dict["explanations"]
    sections = ci_dict["explanation_sections"]

    assert len(explanations) >= 25, f"Expected >= 25 explanations, got {len(explanations)}"
    assert len(sections) >= 6, f"Expected >= 6 sections, got {len(sections)}"

    # Check key concepts are explained
    concept_names = {e["concept"] for e in explanations}
    assert "Ejection Fraction" in concept_names
    assert "Fractional Shortening" in concept_names
    assert "Pulmonary Artery Systolic Pressure" in concept_names
    assert "Mild Tricuspid Regurgitation" in concept_names or "Tricuspid Regurgitation" in concept_names
    assert "Regional Wall Motion Abnormality" in concept_names
    assert "Aortic Regurgitation" in concept_names
    assert "Pulmonary Regurgitation" in concept_names
    assert "Pericardial Effusion" in concept_names
    assert "Thrombus" in concept_names

    # Check that all explanations pass the safety / factuality check
    for exp in explanations:
        text = exp.get("explanation", "").lower()
        for forbidden in FORBIDDEN_WORDS:
            assert forbidden not in text, f"Forbidden word '{forbidden}' in explanation: {exp['explanation']}"
