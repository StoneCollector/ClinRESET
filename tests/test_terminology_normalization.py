"""
tests/test_terminology_normalization.py

Comprehensive test suite for Phase 3/4 terminology normalization and
contextual abbreviation disambiguation subsystem.

Covers:
1. Direct abbreviation expansion
2. Case variation
3. Ambiguous abbreviations
4. Report-type-specific disambiguation
5. Unknown abbreviations
6. Multiple candidate meanings preservation
7. Existing Phase 3 regression cases
8. Echocardiography-specific terminology prioritization
9. Joint Commission safety / error-prone abbreviations
10. Strict separation from clinical interpretation
11. 8-level context resolution hierarchy
12. End-to-end integration with clinical extraction
"""

import pytest

from clinical_extraction.extractor import extract_clinical_info
from clinical_extraction.models import (
    AmbiguityStatus,
    ClinicalEntity,
    ClinicalFinding,
    ClinicalMeasurement,
    EntityType,
)
from clinical_extraction.normalization import normalize_term, resolve_term
from clinical_extraction.terminology import (
    ResolutionContext,
    ResolutionResult,
    TerminologyCorpus,
    get_corpus,
    get_resolver,
)
from extraction.models import DocumentMeta, ExtractionResult, Section, ValidationResult
from classification.models import ClassificationResult


# ---------------------------------------------------------------------------
# Test 1: Direct Abbreviation Expansion
# ---------------------------------------------------------------------------


class TestDirectAbbreviationExpansion:
    """Verifies that unambiguous abbreviations expand directly to canonical terms."""

    def test_lvh_direct_expansion(self):
        res = resolve_term("LVH")
        assert res.text == "LVH"
        assert res.normalized == "Left Ventricular Hypertrophy"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED
        assert res.normalization_source == "terminology_corpus"
        assert "Left Ventricular Hypertrophy" in res.candidates

    def test_rwma_direct_expansion(self):
        res = resolve_term("RWMA")
        assert res.text == "RWMA"
        assert res.normalized == "Regional Wall Motion Abnormality"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_ef_direct_expansion(self):
        res = resolve_term("EF")
        assert res.text == "EF"
        assert res.normalized == "Ejection Fraction"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_provenance_is_preserved(self):
        res = resolve_term("LVH")
        assert res.provenance is not None
        assert "corpus_unambiguous" in res.provenance or "line" in res.provenance


# ---------------------------------------------------------------------------
# Test 2: Case Variation
# ---------------------------------------------------------------------------


class TestCaseVariation:
    """Verifies case-insensitive matching while strictly preserving source surface form."""

    @pytest.mark.parametrize("input_text", ["lvh", "LVH", "Lvh", "lVh"])
    def test_lvh_case_variations(self, input_text):
        res = resolve_term(input_text)
        # Original surface form MUST be preserved
        assert res.text == input_text
        # Standardized term must be in canonical Title Case
        assert res.normalized == "Left Ventricular Hypertrophy"
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    @pytest.mark.parametrize("input_text", ["ef", "EF", "Ef"])
    def test_ef_case_variations(self, input_text):
        res = resolve_term(input_text)
        assert res.text == input_text
        assert res.normalized == "Ejection Fraction"
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    @pytest.mark.parametrize("input_text", ["tapse", "TAPSE", "Tapse"])
    def test_tapse_case_variations(self, input_text):
        res = resolve_term(input_text)
        assert res.text == input_text
        assert res.normalized == "Tricuspid Annular Plane Systolic Excursion"
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED


# ---------------------------------------------------------------------------
# Test 3: Ambiguous Abbreviations Without Context
# ---------------------------------------------------------------------------


class TestAmbiguousAbbreviations:
    """Verifies that ambiguous abbreviations preserve candidate meanings without guessing."""

    def test_ra_without_context_is_ambiguous(self):
        res = resolve_term("RA")
        assert res.text == "RA"
        # Must NOT guess when context is missing
        assert res.normalized is None
        assert res.ambiguity is True
        assert res.ambiguity_status == AmbiguityStatus.AMBIGUOUS
        # Preserves known candidates
        assert "Right Atrium" in res.candidates
        assert "Rheumatoid Arthritis" in res.candidates
        assert "Radium" in res.candidates

    def test_ms_without_context_is_ambiguous(self):
        res = resolve_term("MS")
        assert res.text == "MS"
        assert res.normalized is None
        assert res.ambiguity is True
        assert res.ambiguity_status == AmbiguityStatus.AMBIGUOUS
        assert "Mitral Stenosis" in res.candidates
        assert "Multiple Sclerosis" in res.candidates

    def test_ca_without_context_is_ambiguous(self):
        res = resolve_term("CA")
        assert res.text == "CA"
        assert res.normalized is None
        assert res.ambiguity is True
        assert res.ambiguity_status == AmbiguityStatus.AMBIGUOUS
        assert "Cancer" in res.candidates
        assert "Calcium" in res.candidates

    def test_pa_without_context_is_ambiguous(self):
        res = resolve_term("PA")
        assert res.text == "PA"
        assert res.normalized is None
        assert res.ambiguity is True
        assert res.ambiguity_status == AmbiguityStatus.AMBIGUOUS
        assert "Pulmonary Artery" in res.candidates
        assert "Posteroanterior" in res.candidates


# ---------------------------------------------------------------------------
# Test 4: Report-Type-Specific Disambiguation
# ---------------------------------------------------------------------------


class TestReportTypeSpecificDisambiguation:
    """Verifies that report type correctly disambiguates competing candidates."""

    def test_ra_in_echocardiography(self):
        res = resolve_term("RA", report_type="echocardiography")
        assert res.text == "RA"
        assert res.normalized == "Right Atrium"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_ra_in_rheumatology(self):
        res = resolve_term("RA", report_type="rheumatology")
        assert res.text == "RA"
        assert res.normalized == "Rheumatoid Arthritis"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_ms_in_echocardiography(self):
        res = resolve_term("MS", report_type="echocardiography")
        assert res.text == "MS"
        assert res.normalized == "Mitral Stenosis"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_ms_in_neurology(self):
        res = resolve_term("MS", report_type="neurology")
        assert res.text == "MS"
        assert res.normalized == "Multiple Sclerosis"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_ca_in_laboratory(self):
        res = resolve_term("CA", report_type="laboratory")
        assert res.text == "CA"
        assert res.normalized == "Calcium"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_ca_in_oncology(self):
        res = resolve_term("CA", report_type="oncology")
        assert res.text == "CA"
        assert res.normalized == "Cancer"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_pa_in_echocardiography(self):
        res = resolve_term("PA", report_type="echocardiography")
        assert res.text == "PA"
        assert res.normalized == "Pulmonary Artery"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_pa_in_radiology(self):
        res = resolve_term("PA", report_type="radiology")
        assert res.text == "PA"
        assert res.normalized == "Posteroanterior"
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED


# ---------------------------------------------------------------------------
# Test 5: Unknown Abbreviations
# ---------------------------------------------------------------------------


class TestUnknownAbbreviations:
    """Verifies that unknown abbreviations are not forced into existing concepts."""

    def test_unknown_abbreviation_not_forced(self):
        res = resolve_term("XYZ_NONEXISTENT_ABBR")
        assert res.text == "XYZ_NONEXISTENT_ABBR"
        assert res.normalized is None
        assert res.ambiguity is False
        assert res.ambiguity_status == AmbiguityStatus.UNKNOWN
        assert res.candidates == []
        assert res.provenance == "unknown_term_not_in_corpus"

    def test_normalize_term_returns_none_for_unknown(self):
        assert normalize_term("PseudoXylocephalyNonexistent") is None
        assert normalize_term("ABCD1234XYZ") is None

    def test_non_applicable_tokens(self):
        res = resolve_term("%")
        assert res.ambiguity_status == AmbiguityStatus.NOT_APPLICABLE
        assert res.normalized is None

        res_num = resolve_term("123.45")
        assert res_num.ambiguity_status == AmbiguityStatus.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Test 6: Multiple Candidate Meanings Preservation
# ---------------------------------------------------------------------------


class TestMultipleCandidateMeanings:
    """Verifies candidate concepts structure and serialization."""

    def test_candidate_list_structure(self):
        res = resolve_term("RA")
        d = res.to_dict()
        assert d["text"] == "RA"
        assert d["normalized"] is None
        assert d["ambiguity"] is True
        assert d["ambiguity_status"] == AmbiguityStatus.AMBIGUOUS
        assert isinstance(d["candidates"], list)
        assert len(d["candidates"]) >= 3
        assert "Right Atrium" in d["candidates"]
        assert "Rheumatoid Arthritis" in d["candidates"]
        assert "Radium" in d["candidates"]

    def test_resolved_candidate_preserves_options(self):
        res = resolve_term("RA", report_type="echocardiography")
        d = res.to_dict()
        assert d["text"] == "RA"
        assert d["normalized"] == "Right Atrium"
        assert d["ambiguity"] is False
        assert d["ambiguity_status"] == AmbiguityStatus.RESOLVED
        # Candidates list should still record what options existed
        assert "Right Atrium" in d["candidates"]
        assert "Rheumatoid Arthritis" in d["candidates"]


# ---------------------------------------------------------------------------
# Test 7: Existing Phase 3 Regression Cases
# ---------------------------------------------------------------------------


class TestPhase3Regressions:
    """Verifies full backward compatibility with all Phase 3 normalization calls."""

    def test_echo_standard_abbreviations(self):
        assert normalize_term("EF", "echocardiography") == "Ejection Fraction"
        assert normalize_term("TR", "echocardiography") == "Tricuspid Regurgitation"
        assert normalize_term("LVH", "echocardiography") == "Left Ventricular Hypertrophy"
        assert normalize_term("RWMA", "echocardiography") == "Regional Wall Motion Abnormality"
        assert normalize_term("LVDD", "echocardiography") == "Left Ventricular Diastolic Dysfunction"
        assert normalize_term("PASP", "echocardiography") == "Pulmonary Artery Systolic Pressure"

    def test_qualified_terms(self):
        assert normalize_term("Conc LVH", "echocardiography") == "Concentric Left Ventricular Hypertrophy"
        assert normalize_term("Mild TR", "echocardiography") == "Mild Tricuspid Regurgitation"
        assert normalize_term("Grade 1 LVDD", "echocardiography") == "Grade 1 Left Ventricular Diastolic Dysfunction"

    def test_universal_fallback_when_unambiguous(self):
        # Multi-word phrase that is completely unambiguous
        assert normalize_term("ejection fraction") == "Ejection Fraction"
        assert normalize_term("fractional shortening") == "Fractional Shortening"

    def test_ambiguous_term_returns_none_without_context(self):
        # 'RA' must NOT resolve to 'Right Atrium' without context
        assert normalize_term("RA") is None


# ---------------------------------------------------------------------------
# Test 8: Echocardiography-Specific Terminology Prioritization
# ---------------------------------------------------------------------------


class TestEchoSpecificTerminology:
    """Verifies exact prioritization of all 11 required echocardiography terms."""

    REQUIRED_ECHO_TERMS = [
        ("EF", "Ejection Fraction"),
        ("LVEF", "Left Ventricular Ejection Fraction"),
        ("LVH", "Left Ventricular Hypertrophy"),
        ("RWMA", "Regional Wall Motion Abnormality"),
        ("LVDD", "Left Ventricular Diastolic Dysfunction"),
        ("TR", "Tricuspid Regurgitation"),
        ("MR", "Mitral Regurgitation"),
        ("AR", "Aortic Regurgitation"),
        ("PASP", "Pulmonary Artery Systolic Pressure"),
        ("TAPSE", "Tricuspid Annular Plane Systolic Excursion"),
        ("LVOT", "Left Ventricular Outflow Tract"),
    ]

    @pytest.mark.parametrize("abbr,expected_norm", REQUIRED_ECHO_TERMS)
    def test_required_echo_abbreviations(self, abbr, expected_norm):
        res = resolve_term(abbr, report_type="echocardiography")
        assert res.normalized == expected_norm
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_cardiac_anatomy_abbreviations(self):
        assert resolve_term("LV", report_type="echocardiography").normalized == "Left Ventricle"
        assert resolve_term("RV", report_type="echocardiography").normalized == "Right Ventricle"
        assert resolve_term("LA", report_type="echocardiography").normalized == "Left Atrium"
        assert resolve_term("IAS", report_type="echocardiography").normalized == "Interatrial Septum"
        assert resolve_term("IVS", report_type="echocardiography").normalized == "Interventricular Septum"


# ---------------------------------------------------------------------------
# Test 9: Safety and Error-Prone Abbreviations
# ---------------------------------------------------------------------------


class TestSafetyAndErrorProneAbbreviations:
    """Verifies Joint Commission 'Do Not Use' list handling and alerts."""

    def test_mso4_safety_alert(self):
        res = resolve_term("MSO4")
        assert res.safety_warning is not None
        assert "Joint Commission" in res.safety_warning
        # MSO4 is error prone and prohibited - must be flagged as ambiguous
        assert res.ambiguity is True
        assert res.ambiguity_status == AmbiguityStatus.AMBIGUOUS

    def test_mgso4_safety_alert(self):
        res = resolve_term("MgSO4")
        assert res.safety_warning is not None
        assert "Joint Commission" in res.safety_warning

    def test_u_safety_alert(self):
        res = resolve_term("U")
        assert res.safety_warning is not None
        assert "Joint Commission" in res.safety_warning

    def test_iu_safety_alert(self):
        res = resolve_term("IU")
        assert res.safety_warning is not None
        assert "Joint Commission" in res.safety_warning

    def test_qd_safety_alert(self):
        res = resolve_term("QD")
        assert res.safety_warning is not None
        assert "Joint Commission" in res.safety_warning

    def test_qod_safety_alert(self):
        res = resolve_term("QOD")
        assert res.safety_warning is not None
        assert "Joint Commission" in res.safety_warning


# ---------------------------------------------------------------------------
# Test 10: Non-Inference / No Clinical Interpretation Constraint
# ---------------------------------------------------------------------------


class TestNoClinicalInterpretation:
    """
    CRITICAL ARCHITECTURAL CONSTRAINT:
    Terminology normalization answers 'What standardized concept does this surface form refer to?'
    It must NOT infer diagnosis, severity, normal/abnormal status, risk, or prognosis.
    """

    def test_lvh_does_not_infer_severity_or_clinical_commentary(self):
        res = resolve_term("LVH")
        assert res.normalized == "Left Ventricular Hypertrophy"
        # Must not contain clinical interpretations
        assert "enlarged" not in res.normalized.lower()
        assert "concerning" not in res.normalized.lower()
        assert "abnormal" not in res.normalized.lower()
        assert "risk" not in res.normalized.lower()

    def test_rwma_does_not_infer_infarction_or_ischemia(self):
        res = resolve_term("RWMA")
        assert res.normalized == "Regional Wall Motion Abnormality"
        assert "infarct" not in res.normalized.lower()
        assert "ischemia" not in res.normalized.lower()

    def test_mild_tr_preserves_only_linguistic_degree(self):
        res = resolve_term("Mild TR", report_type="echocardiography")
        assert res.normalized == "Mild Tricuspid Regurgitation"
        # Does not convert mild into normal/abnormal judgment
        assert "normal" not in res.normalized.lower()
        assert "abnormal" not in res.normalized.lower()


# ---------------------------------------------------------------------------
# Test 11: 8-Level Context Resolution Hierarchy
# ---------------------------------------------------------------------------


class TestContextResolutionHierarchy:
    """Verifies that lower-priority signals resolve when higher ones are absent."""

    def test_level_2_section_title_disambiguates(self):
        # No report_type, but section_title='CARDIAC VALVES'
        res = resolve_term("MS", section_title="CARDIAC VALVES")
        assert res.normalized == "Mitral Stenosis"
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_level_2_neurology_section_disambiguates(self):
        res = resolve_term("MS", section_title="NEUROLOGY EVALUATION")
        assert res.normalized == "Multiple Sclerosis"
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_level_3_nearby_text_disambiguates(self):
        # No report_type or section, but nearby text mentions mitral valve
        res = resolve_term("MS", nearby_text="The mitral valve area was severely narrowed")
        assert res.normalized == "Mitral Stenosis"
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_level_4_anatomy_context_disambiguates(self):
        ctx = ResolutionContext(anatomy_context=["right atrium", "mitral valve"])
        res = resolve_term("RA", context=ctx)
        assert res.normalized == "Right Atrium"
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED

    def test_level_5_measurement_context_disambiguates(self):
        # Serum calcium test context with mg/dL
        ctx = ResolutionContext(measurement_context=["Calcium 9.2 mg/dL", "Serum Albumin"])
        res = resolve_term("CA", context=ctx)
        assert res.normalized == "Calcium"
        assert res.ambiguity_status == AmbiguityStatus.RESOLVED


# ---------------------------------------------------------------------------
# Test 12: End-to-End Extraction Integration
# ---------------------------------------------------------------------------


class TestExtractionIntegration:
    """Verifies that extractor produces structured normalization fields on all items."""

    def test_extracted_findings_have_normalization_metadata(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            classification=ClassificationResult(
                report_type="echocardiography",
                confidence=1.0,
                status="CONFIDENT",
            ),
            sections=[
                Section(title="IMPRESSION", page=1, text="- LVH\n- No RWMA\n- Mild TR"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)

        # Check findings
        assert len(ci.findings) >= 2
        for f in ci.findings:
            d = f.to_dict()
            assert "text" in d
            assert "normalized" in d
            assert "normalization_source" in d
            assert "ambiguity" in d
            assert "ambiguity_status" in d
            assert d["ambiguity_status"] in AmbiguityStatus.ALL

        lvh_finding = next((f for f in ci.findings if "LVH" in f.text), None)
        assert lvh_finding is not None
        assert lvh_finding.normalized == "Left Ventricular Hypertrophy"
        assert lvh_finding.ambiguity is False
        assert lvh_finding.ambiguity_status == AmbiguityStatus.RESOLVED
        assert lvh_finding.normalization_source is not None

    def test_extracted_measurements_have_normalization_metadata(self):
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            classification=ClassificationResult(
                report_type="echocardiography",
                confidence=1.0,
                status="CONFIDENT",
            ),
            sections=[
                Section(title="MEASUREMENTS", page=1, text="EF = 60%\nPASP = 35 mmHg"),
            ],
            measurements=[
                {"name": "EF", "value": 60, "unit": "%", "page": 1, "source_section": "MEASUREMENTS"},
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)

        assert len(ci.measurements) >= 1
        m = ci.measurements[0]
        d = m.to_dict()
        assert d["name"] == "EF"
        assert d["normalized_name"] == "Ejection Fraction"
        assert d["ambiguity"] is False
        assert d["ambiguity_status"] == AmbiguityStatus.RESOLVED
        assert d["normalization_source"] is not None

    def test_ambiguous_entity_in_report_preserves_candidates(self):
        # Unclassified report containing 'MS' with no other clues
        doc = ExtractionResult(
            document=DocumentMeta("test.pdf", 1, "digital_pdf", "pymupdf4llm"),
            classification=None,
            sections=[
                Section(title="HISTORY", page=1, text="Patient with history of MS"),
            ],
            validation=ValidationResult(status="GOOD"),
        )
        ci = extract_clinical_info(doc)
        ms_entities = [e for e in ci.entities if e.text == "MS"]
        if ms_entities:
            ms = ms_entities[0]
            assert ms.ambiguity is True
            assert ms.ambiguity_status == AmbiguityStatus.AMBIGUOUS
            assert len(ms.candidates) >= 2


# ---------------------------------------------------------------------------
# Test 13: Corpus Loader Metrics and Statistics
# ---------------------------------------------------------------------------


class TestCorpusStatistics:
    """Verifies that the corpus loads accurately with all required metrics."""

    def test_corpus_record_counts(self):
        corpus = get_corpus()
        assert corpus.raw_record_count == 578
        assert len(corpus.records_by_surface_form) >= 550
        assert corpus.ambiguous_records_count > 0
        assert corpus.report_specific_mappings_count > 0
