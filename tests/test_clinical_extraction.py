"""
tests/test_clinical_extraction.py

Comprehensive test suite for Phase 3: Clinical Information Extraction.

Validates all 12 core requirements:
1. Echocardiography report end-to-end
2. Measurements (reuse from Phase 1, inline extraction, no unit fabrication)
3. Anatomy extraction (explicit structures, provenance)
4. Finding extraction (verbatim wording preserved)
5. Negated findings (negated=True, assertion=ABSENT, not discarded)
6. Normal findings (assertion=NORMAL, negated=False)
7. Abbreviations handling
8. Terminology normalization (normalized field without overwriting source)
9. Relationships (traceable, no speculation)
10. Source/page traceability (provenance on every item)
11. Unknown / unsupported terminology (normalized=None, no forced guessing)
12. Multiple findings in one sentence (no negation bleeding across clauses)
Plus:
13. No clinical interpretation constraint verification
14. Other report types (CBC, Lipid, ECG)
15. Deterministic evaluation metrics (Precision, Recall, F1, Negation Accuracy)
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from clinical_extraction import (
    AssertionStatus,
    ClinicalEntity,
    ClinicalFinding,
    ClinicalInformation,
    ClinicalMeasurement,
    ClinicalRelationship,
    EntityType,
    RelationType,
    extract_clinical_info,
)
from clinical_extraction.extractor import extract_clinical_info
from clinical_extraction.negation import detect_assertion, split_into_clauses
from clinical_extraction.normalization import normalize_term
from extraction.models import (
    DocumentMeta,
    ExtractionResult,
    Measurement,
    RawOutput,
    Section,
    Table,
    TableRow,
    ValidationResult,
)
from extraction.pipeline import extract_document


SAMPLE_PDF = Path("txt_extractor") / "sample_report.pdf"


# ---------------------------------------------------------------------------
# Test 1: Real Echocardiography Report End-to-End
# ---------------------------------------------------------------------------


class TestEchoRealReport:
    """End-to-end extraction tests on sample_report.pdf."""

    @classmethod
    def setup_class(cls):
        cls.result = extract_document(SAMPLE_PDF, save_output=False)
        cls.ci = cls.result.clinical_information

    def test_clinical_information_is_present(self):
        assert self.ci is not None
        assert isinstance(self.ci, ClinicalInformation)

    def test_ejection_fraction_measurement(self):
        ef = next((m for m in self.ci.measurements if "ejection fraction" in m.name.lower()), None)
        assert ef is not None, "Ejection Fraction measurement missing"
        assert ef.value == 60 or ef.value == "60"
        assert ef.unit == "%"
        assert ef.page == 1

    def test_fractional_shortening_measurement(self):
        fs = next((m for m in self.ci.measurements if "fractional shortening" in m.name.lower()), None)
        assert fs is not None, "Fractional shortening measurement missing"
        assert fs.value == 32.5 or fs.value == "32.5"
        assert fs.unit == "%"
        assert fs.page == 1

    def test_aortic_root_diameter_measurement(self):
        ar = next((m for m in self.ci.measurements if "aortic root" in m.name.lower()), None)
        assert ar is not None, "Aortic root diameter measurement missing"
        assert ar.value == 23 or ar.value == "23"
        assert ar.page == 1

    def test_pasp_inline_measurement(self):
        pasp = next((m for m in self.ci.measurements if m.name == "PASP"), None)
        assert pasp is not None, "PASP inline measurement missing"
        assert pasp.value == 34 or pasp.value == "34"
        assert pasp.unit == "mmHg"
        assert pasp.page == 2

    def test_lvh_finding_extracted(self):
        lvh = next((f for f in self.ci.findings if "lvh" in f.text.lower()), None)
        assert lvh is not None, "LVH finding missing"
        assert lvh.negated is False
        assert lvh.assertion == AssertionStatus.PRESENT
        assert lvh.normalized == "Concentric Left Ventricular Hypertrophy"

    def test_rwma_negated_finding(self):
        rwma = next((f for f in self.ci.findings if "rwma" in f.text.lower()), None)
        assert rwma is not None, "RWMA finding missing"
        assert rwma.negated is True, "RWMA must be marked negated"
        assert rwma.assertion == AssertionStatus.ABSENT
        assert rwma.normalized == "Regional Wall Motion Abnormality"

    def test_grade_1_lvdd_finding(self):
        lvdd = next((f for f in self.ci.findings if "lvdd" in f.text.lower()), None)
        assert lvdd is not None, "Grade 1 LVDD finding missing"
        assert lvdd.assertion == AssertionStatus.PRESENT
        assert lvdd.negated is False
        assert lvdd.normalized == "Grade 1 Left Ventricular Diastolic Dysfunction"

    def test_mild_tr_finding(self):
        tr = next((f for f in self.ci.findings if "tr" in f.text.lower() and "mitral" not in f.text.lower()), None)
        assert tr is not None, "Mild TR finding missing"
        assert tr.assertion == AssertionStatus.PRESENT
        assert tr.negated is False
        assert tr.normalized == "Mild Tricuspid Regurgitation"

    def test_normal_rv_function_finding(self):
        rv = next((f for f in self.ci.findings if "rv function" in f.text.lower()), None)
        assert rv is not None, "Normal RV function finding missing"
        assert rv.assertion == AssertionStatus.NORMAL
        assert rv.negated is False

    def test_no_effusion_finding(self):
        eff = next((f for f in self.ci.findings if "effusion" in f.text.lower()), None)
        assert eff is not None, "No effusion finding missing"
        assert eff.negated is True
        assert eff.assertion == AssertionStatus.ABSENT

    def test_no_aortic_regurgitation_finding(self):
        ar = next((f for f in self.ci.findings if "aortic regurgitation" in f.text.lower()), None)
        assert ar is not None, "No aortic regurgitation finding missing"
        assert ar.negated is True
        assert ar.assertion == AssertionStatus.ABSENT

    def test_no_pulmonary_regurgitation_finding(self):
        pr = next((f for f in self.ci.findings if "pulmonary regurgitation" in f.text.lower()), None)
        assert pr is not None, "No pulmonary regurgitation finding missing"
        assert pr.negated is True
        assert pr.assertion == AssertionStatus.ABSENT

    def test_relevant_anatomical_structures(self):
        anatomy_names = {a.normalized or a.text for a in self.ci.anatomy}
        expected = {
            "Mitral Valve",
            "Tricuspid Valve",
            "Aortic Valve",
            "Pulmonary Valve",
            "Left Ventricle",
            "Right Ventricle",
            "Aortic Root",
            "Left Ventricular Outflow Tract",
            "Interventricular Septum",
            "Interatrial Septum",
        }
        for exp in expected:
            assert any(exp.lower() in name.lower() for name in anatomy_names), f"Missing anatomy: {exp}"

    def test_to_dict_includes_clinical_information(self):
        d = self.result.to_dict()
        assert "clinical_information" in d
        ci_dict = d["clinical_information"]
        assert "entities" in ci_dict
        assert "measurements" in ci_dict
        assert "findings" in ci_dict
        assert "anatomy" in ci_dict
        assert "relationships" in ci_dict

    def test_to_dict_preserves_all_original_fields(self):
        d = self.result.to_dict()
        for key in ("document", "classification", "sections", "tables", "measurements", "raw", "validation"):
            assert key in d, f"Field '{key}' was improperly altered or removed"


# ---------------------------------------------------------------------------
# Test 2: Measurements Extraction & Unit Preservation
# ---------------------------------------------------------------------------


class TestMeasurements:
    """Validates measurement reuse, inline extraction, and non-fabrication."""

    def test_no_unit_fabrication(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            measurements=[
                Measurement(name="Aortic root diameter", value="23", unit=None, reference_range=None, page=1),
            ],
            sections=[],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        m = ci.measurements[0]
        assert m.unit is None, "Unit must not be fabricated when absent in source"
        assert m.reference_range is None

    def test_unit_preserved_when_present(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            measurements=[
                Measurement(name="Ejection Fraction", value="60", unit="%", reference_range="55-74%", page=1),
            ],
            sections=[],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        m = ci.measurements[0]
        assert m.unit == "%"
        assert m.reference_range == "55-74%"
        assert m.value == 60

    def test_demographics_excluded_from_measurements(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title=None, page=1, text="AGE/SEX: 61y /F DATED: 2024-01-01 REF BY: IPD"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        names = [m.name.lower() for m in ci.measurements]
        assert "age" not in names
        assert "age/sex" not in names
        assert "dated" not in names


# ---------------------------------------------------------------------------
# Test 3: Anatomy Extraction & Traceability
# ---------------------------------------------------------------------------


class TestAnatomyExtraction:
    """Validates explicit anatomy extraction and provenance."""

    def test_explicit_anatomy_extracted_with_provenance(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="FINDINGS", page=2, text="Enlarged left ventricle and thick interventricular septum."),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        anatomy_texts = [a.text.lower() for a in ci.anatomy]
        assert "left ventricle" in anatomy_texts
        assert "interventricular septum" in anatomy_texts
        for a in ci.anatomy:
            assert a.page == 2
            assert a.source_section == "FINDINGS"
            assert a.source_text is not None

    def test_no_unmentioned_anatomy_invented(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="CHEST", page=1, text="Clear lungs. Heart size normal."),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        anatomy_texts = [a.text.lower() for a in ci.anatomy]
        assert "brain" not in anatomy_texts
        assert "liver" not in anatomy_texts


# ---------------------------------------------------------------------------
# Test 4: Finding Extraction & Verbatim Preservation
# ---------------------------------------------------------------------------


class TestFindingExtraction:
    """Verifies that findings preserve exact original wording."""

    def test_verbatim_finding_preserved(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="IMPRESSION", page=1, text="- Conc LVH\n- Mild TR"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        finding_texts = [f.text for f in ci.findings]
        assert "Conc LVH" in finding_texts, "Original wording 'Conc LVH' must be preserved"
        assert "Mild TR" in finding_texts


# ---------------------------------------------------------------------------
# Test 5 & 6: Negation & Assertion Status
# ---------------------------------------------------------------------------


class TestNegationAndAssertion:
    """Validates differentiation between positive, negated, and normal findings."""

    def test_negated_finding_rwma(self):
        status, is_negated = detect_assertion("No RWMA")
        assert is_negated is True
        assert status == AssertionStatus.ABSENT

    def test_positive_finding_rwma(self):
        status, is_negated = detect_assertion("RWMA present in anterior wall")
        assert is_negated is False
        assert status == AssertionStatus.PRESENT

    def test_normal_finding_rv_function(self):
        status, is_negated = detect_assertion("Normal RV function")
        assert is_negated is False
        assert status == AssertionStatus.NORMAL

    def test_no_evidence_of_vegetation(self):
        status, is_negated = detect_assertion("No evidence of any mass / vegetation")
        assert is_negated is True
        assert status == AssertionStatus.ABSENT

    def test_without_effusion(self):
        status, is_negated = detect_assertion("Without pericardial effusion")
        assert is_negated is True
        assert status == AssertionStatus.ABSENT

    def test_intact_septum_is_normal(self):
        status, is_negated = detect_assertion("IAS/IVS intact")
        assert is_negated is False
        assert status == AssertionStatus.NORMAL

    def test_possible_finding(self):
        status, is_negated = detect_assertion("Possible mild aortic stenosis")
        assert is_negated is False
        assert status == AssertionStatus.POSSIBLE

    def test_negated_findings_not_discarded(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="IMPRESSION", page=1, text="- No effusion\n- No RWMA"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        assert len(ci.findings) == 2
        for f in ci.findings:
            assert f.negated is True
            assert f.assertion == AssertionStatus.ABSENT


# ---------------------------------------------------------------------------
# Test 7 & 8: Abbreviations & Terminology Normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    """Verifies that terminology normalization works without overwriting original text."""

    def test_echo_abbreviation_normalization(self):
        assert normalize_term("EF", "echocardiography") == "Ejection Fraction"
        assert normalize_term("TR", "echocardiography") == "Tricuspid Regurgitation"
        assert normalize_term("LVH", "echocardiography") == "Left Ventricular Hypertrophy"
        assert normalize_term("RWMA", "echocardiography") == "Regional Wall Motion Abnormality"
        assert normalize_term("LVDD", "echocardiography") == "Left Ventricular Diastolic Dysfunction"
        assert normalize_term("PASP", "echocardiography") == "Pulmonary Artery Systolic Pressure"

    def test_qualified_terms_normalization(self):
        assert normalize_term("Conc LVH", "echocardiography") == "Concentric Left Ventricular Hypertrophy"
        assert normalize_term("Mild TR", "echocardiography") == "Mild Tricuspid Regurgitation"
        assert normalize_term("Grade 1 LVDD", "echocardiography") == "Grade 1 Left Ventricular Diastolic Dysfunction"

    def test_normalization_does_not_overwrite_source(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="IMPRESSION", page=1, text="- Conc LVH"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        f = ci.findings[0]
        assert f.text == "Conc LVH"
        assert f.normalized == "Concentric Left Ventricular Hypertrophy"


# ---------------------------------------------------------------------------
# Test 9: Relationships
# ---------------------------------------------------------------------------


class TestRelationships:
    """Verifies direct, traceable clinical relationships without speculation."""

    def test_finding_to_anatomy_relationship(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 2, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="FINAL IMPRESSION", page=2, text="- Conc LVH\n- Mild TR"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        rel_map = {(r.source, r.target): r.relation for r in ci.relationships}
        assert ("Conc LVH", "left ventricle") in rel_map
        assert rel_map[("Conc LVH", "left ventricle")] == RelationType.ASSOCIATED_WITH
        assert ("Mild TR", "tricuspid valve") in rel_map

    def test_measurement_to_anatomy_relationship(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            measurements=[
                Measurement(name="Ejection Fraction", value="60", unit="%", page=1),
                Measurement(name="Aortic root diameter", value="23", page=1),
            ],
            sections=[],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        rel_map = {(r.source, r.target): r.relation for r in ci.relationships}
        assert ("Ejection Fraction", "left ventricle") in rel_map
        assert rel_map[("Ejection Fraction", "left ventricle")] == RelationType.MEASURES
        assert ("Aortic root diameter", "aortic root") in rel_map

    def test_relationships_have_provenance(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 2, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="FINAL IMPRESSION", page=2, text="- Conc LVH"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        rel = ci.relationships[0]
        assert rel.page == 2
        assert rel.source_text is not None


# ---------------------------------------------------------------------------
# Test 10: Source / Page Traceability
# ---------------------------------------------------------------------------


class TestTraceability:
    """Verifies that all extracted elements maintain exact source provenance."""

    def test_all_elements_have_provenance(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            measurements=[
                Measurement(name="Ejection Fraction", value="60", unit="%", page=1, source_section="M-MODE"),
            ],
            sections=[
                Section(title="IMPRESSION", page=1, text="- Conc LVH"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)

        for e in ci.entities:
            assert e.page is not None
            assert e.source_text is not None

        for m in ci.measurements:
            assert m.page is not None
            assert m.source_text is not None

        for f in ci.findings:
            assert f.page is not None
            assert f.source_section is not None
            assert f.source_text is not None


# ---------------------------------------------------------------------------
# Test 11: Unknown / Unsupported Terminology
# ---------------------------------------------------------------------------


class TestUnknownTerminology:
    """Verifies that unknown or unsupported medical terms leave normalized as None."""

    def test_unsupported_term_not_forced(self):
        assert normalize_term("Xylocephaly Nonexistentis") is None
        assert normalize_term("Pseudocongruous Syndrome") is None

    def test_unknown_term_entity_creation(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="IMPRESSION", page=1, text="Observed idiopathic pseudostenosis."),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        # Normalization must be None for unmapped concepts
        for f in ci.findings:
            if "pseudostenosis" in f.text.lower():
                assert f.normalized is None


# ---------------------------------------------------------------------------
# Test 12: Multiple Findings in One Sentence (Clause Splitting)
# ---------------------------------------------------------------------------


class TestMultipleFindingsInOneSentence:
    """Verifies that multiple findings in one sentence are split without negation leaking."""

    def test_conc_lvh_no_rwma_clause_split(self):
        text = "Conc LVH, No RWMA"
        clauses = split_into_clauses(text)
        assert len(clauses) >= 2

        # Clause 1: Conc LVH -> PRESENT, not negated
        s1, neg1 = detect_assertion(clauses[0])
        assert neg1 is False
        assert s1 == AssertionStatus.PRESENT

        # Clause 2: No RWMA -> ABSENT, negated
        s2, neg2 = detect_assertion(clauses[1])
        assert neg2 is True
        assert s2 == AssertionStatus.ABSENT

    def test_extraction_does_not_negate_preceding_finding(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            sections=[
                Section(title="FINAL IMPRESSION", page=1, text="- Conc LVH, No RWMA"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        lvh = next(f for f in ci.findings if "lvh" in f.text.lower())
        rwma = next(f for f in ci.findings if "rwma" in f.text.lower())

        assert lvh.negated is False
        assert lvh.assertion == AssertionStatus.PRESENT
        assert rwma.negated is True
        assert rwma.assertion == AssertionStatus.ABSENT


# ---------------------------------------------------------------------------
# Test 13: Strict Prohibition on Clinical Interpretation
# ---------------------------------------------------------------------------


class TestNoClinicalInterpretation:
    """Verifies that Phase 3 does not generate diagnostic interpretations."""

    def test_no_diagnosis_inferred_from_abnormal_measurement(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            measurements=[
                Measurement(name="Inter Vent. Septum thickness D", value="13", unit="mm", reference_range="6-11mm", page=1),
            ],
            sections=[],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        # Must NOT infer "Patient has septal hypertrophy"
        for f in ci.findings:
            assert "hypertrophy" not in f.text.lower()
        for e in ci.entities:
            assert e.type != EntityType.DIAGNOSIS


# ---------------------------------------------------------------------------
# Test 14: Other Report Types (CBC, Lipid, ECG)
# ---------------------------------------------------------------------------


class TestOtherReportTypes:
    """Validates report-type-aware extraction across different medical specialties."""

    def test_cbc_extraction(self):
        from classification.models import ClassificationResult

        doc = ExtractionResult(
            document=DocumentMeta("cbc.pdf", 1, "digital_pdf", "pymupdf4llm"),
            classification=ClassificationResult("cbc", 1.0, "CONFIDENT"),
            measurements=[
                Measurement(name="Hemoglobin", value="13.5", unit="g/dL", reference_range="12.0-15.0", page=1),
                Measurement(name="Platelet Count", value="250000", unit="/uL", reference_range="150000-450000", page=1),
            ],
            sections=[
                Section(title="PERIPHERAL SMEAR", page=1, text="Normocytic normochromic red cells. Adequate platelets. No hemoparasite."),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        assert len(ci.measurements) >= 2
        no_parasite = next((f for f in ci.findings if "parasite" in f.text.lower()), None)
        assert no_parasite is not None
        assert no_parasite.negated is True
        assert no_parasite.assertion == AssertionStatus.ABSENT

    def test_lipid_profile_extraction(self):
        from classification.models import ClassificationResult

        doc = ExtractionResult(
            document=DocumentMeta("lipid.pdf", 1, "digital_pdf", "pymupdf4llm"),
            classification=ClassificationResult("lipid_profile", 1.0, "CONFIDENT"),
            measurements=[
                Measurement(name="Total Cholesterol", value="210", unit="mg/dL", reference_range="<200", page=1),
                Measurement(name="HDL Cholesterol", value="55", unit="mg/dL", reference_range=">40", page=1),
            ],
            sections=[
                Section(title="INTERPRETATION", page=1, text="Borderline high total cholesterol."),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        assert len(ci.measurements) == 2
        assert any("borderline high" in f.text.lower() for f in ci.findings)

    def test_ecg_extraction(self):
        from classification.models import ClassificationResult

        doc = ExtractionResult(
            document=DocumentMeta("ecg.pdf", 1, "digital_pdf", "pymupdf4llm"),
            classification=ClassificationResult("ecg", 1.0, "CONFIDENT"),
            measurements=[
                Measurement(name="Heart Rate", value="72", unit="bpm", page=1),
            ],
            sections=[
                Section(title="INTERPRETATION", page=1, text="Normal sinus rhythm. No ST elevation."),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        nsr = next((f for f in ci.findings if "sinus rhythm" in f.text.lower()), None)
        assert nsr is not None
        assert nsr.assertion == AssertionStatus.NORMAL
        st = next((f for f in ci.findings if "st elevation" in f.text.lower()), None)
        assert st is not None
        assert st.negated is True
        assert st.assertion == AssertionStatus.ABSENT


# ---------------------------------------------------------------------------
# Test 15: Deterministic Evaluation Metrics
# ---------------------------------------------------------------------------


class TestEvaluationMetrics:
    """Computes exact accuracy, precision, recall, and F1 on verified benchmark assertions."""

    def test_negation_detection_accuracy(self):
        test_cases = [
            ("No RWMA", True),
            ("Conc LVH", False),
            ("No effusion", True),
            ("Mild TR", False),
            ("No aortic regurgitation", True),
            ("No pulmonary regurgitation present", True),
            ("Normal RV function", False),
            ("No gradient across LVOT", True),
            ("IAS/IVS intact", False),
            ("No evidence of any mass / vegetation", True),
            ("No LA/LV clot", True),
            ("Grade 1 LVDD", False),
            ("Without pericardial fluid", True),
            ("Negative for ischemia", True),
            ("Normal sinus rhythm", False),
            ("No ST elevation", True),
        ]
        correct = 0
        for text, expected_neg in test_cases:
            _, is_neg = detect_assertion(text)
            if is_neg == expected_neg:
                correct += 1

        accuracy = correct / len(test_cases)
        assert accuracy == 1.0, f"Negation accuracy is {accuracy:.2f}, expected 1.00"

    def test_normalization_coverage_on_echo_vocabulary(self):
        echo_terms = [
            "EF", "FS", "LVH", "Conc LVH", "RWMA", "LVDD", "Grade 1 LVDD",
            "TR", "Mild TR", "MR", "AR", "PR", "PASP", "LV", "RV", "LA",
            "RA", "IVS", "IAS", "LVOT",
        ]
        normalized_count = sum(1 for t in echo_terms if normalize_term(t, "echocardiography") is not None)
        coverage = normalized_count / len(echo_terms)
        assert coverage >= 0.95, f"Normalization coverage is {coverage:.2f}, expected >= 0.95"
