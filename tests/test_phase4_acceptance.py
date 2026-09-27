"""
tests/test_phase4_acceptance.py

Phase 4 Acceptance Test Suite: Targeted Semantic Structuring & Output Contract Verification.

Operates directly on the real echocardiography report (sample_report.pdf)
and verifies all 12 acceptance criteria specified in the Phase 4 specification:
 1. Report type is echocardiography
 2. Terminology resolution works
 3. Assertions are preserved (PRESENT, ABSENT, NORMAL)
 4. Measurements are preserved with full numeric values, units, reference ranges
 5. Normalized concepts exist where appropriate
 6. Semantic categories exist and adhere to controlled vocabulary
 7. Relationships correctly link concepts to anatomical sites
 8. Provenance is preserved on every item
 9. Ambiguity is preserved (never guessed)
10. No clinical interpretation is introduced (no risk, abnormality, or prognosis judgment)
11. Original surface text is preserved verbatim
12. Phase 3 behavior has not regressed
Plus:
- Critical context collision test: "EF 60%" vs "Normal 'EF' slope"
- Phase 5 output contract validation
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from clinical_extraction import (
    AmbiguityStatus,
    AssertionStatus,
    ClinicalInformation,
    EntityType,
    RelationType,
    SemanticCategory,
    extract_clinical_info,
    resolve_term,
)
from extraction.pipeline import extract_document


SAMPLE_PDF = Path("txt_extractor") / "sample_report.pdf"


class TestPhase4Acceptance:
    """Comprehensive Phase 4 acceptance test on the real echocardiography sample report."""

    @classmethod
    def setup_class(cls):
        assert SAMPLE_PDF.exists(), f"Sample PDF fixture missing: {SAMPLE_PDF}"
        cls.extraction_result = extract_document(SAMPLE_PDF, save_output=False)
        cls.ci: ClinicalInformation = cls.extraction_result.clinical_information
        assert cls.ci is not None, "ClinicalInformation was not produced"
        cls.concepts = cls.ci.to_phase5_contract()

    # -----------------------------------------------------------------------
    # Criterion 1: Report Type Identification
    # -----------------------------------------------------------------------
    def test_01_report_type_is_echocardiography(self):
        c = self.extraction_result.classification
        assert c is not None
        assert c.report_type == "echocardiography"
        assert c.status == "CONFIDENT"
        assert c.confidence >= 0.90

    # -----------------------------------------------------------------------
    # Criterion 2: Terminology Resolution
    # -----------------------------------------------------------------------
    def test_02_terminology_resolution_core_concepts(self):
        finding_concepts = {f.text: f.normalized for f in self.ci.findings}
        assert finding_concepts.get("Conc LVH") == "Concentric Left Ventricular Hypertrophy"
        assert finding_concepts.get("No RWMA") == "Regional Wall Motion Abnormality"
        assert finding_concepts.get("normal LV function") == "Normal Left Ventricular Function"
        assert finding_concepts.get("Grade 1 LVDD") == "Grade 1 Left Ventricular Diastolic Dysfunction"
        assert finding_concepts.get("Mild TR") == "Mild Tricuspid Regurgitation"
        assert finding_concepts.get("Normal RV function") == "Normal Right Ventricular Function"
        assert finding_concepts.get("No Aortic regurgitation") == "Aortic Regurgitation"
        assert finding_concepts.get("No Pulmonary regurgitation present") == "Pulmonary Regurgitation"
        assert finding_concepts.get("No effusion") == "Pericardial Effusion"
        assert finding_concepts.get("No LA/LV clot") == "Thrombus"
        assert finding_concepts.get("No gradient across LVOT") == "Left Ventricular Outflow Tract Gradient"
        assert finding_concepts.get("IAS/IVS intact") == "Intact Interatrial and Interventricular Septa"

    # -----------------------------------------------------------------------
    # Criterion 3: Assertion Status Preservation
    # -----------------------------------------------------------------------
    def test_03_assertions_preserved(self):
        finding_assertions = {f.text: f.assertion for f in self.ci.findings}

        # Present findings
        assert finding_assertions.get("Conc LVH") == AssertionStatus.PRESENT
        assert finding_assertions.get("Grade 1 LVDD") == AssertionStatus.PRESENT
        assert finding_assertions.get("Mild TR") == AssertionStatus.PRESENT

        # Absent / Negated findings
        assert finding_assertions.get("No RWMA") == AssertionStatus.ABSENT
        assert finding_assertions.get("No Aortic regurgitation") == AssertionStatus.ABSENT
        assert finding_assertions.get("No Pulmonary regurgitation present") == AssertionStatus.ABSENT
        assert finding_assertions.get("No effusion") == AssertionStatus.ABSENT
        assert finding_assertions.get("No LA/LV clot") == AssertionStatus.ABSENT
        assert finding_assertions.get("No gradient across LVOT") == AssertionStatus.ABSENT

        # Normal findings
        assert finding_assertions.get("normal LV function") == AssertionStatus.NORMAL
        assert finding_assertions.get("Normal RV function") == AssertionStatus.NORMAL
        assert finding_assertions.get("IAS/IVS intact") == AssertionStatus.NORMAL

    # -----------------------------------------------------------------------
    # Criterion 4: Measurements Preservation (Values, Units, Reference Ranges)
    # -----------------------------------------------------------------------
    def test_04_measurements_preserved(self):
        meas_map = {m.name: m for m in self.ci.measurements}

        # Aortic root diameter
        ar = meas_map.get("Aortic root diameter")
        assert ar is not None
        assert ar.value in (23, "23")
        assert "20-37" in (ar.reference_range or "")

        # Left Atrial diameter
        la = meas_map.get("Left Atrial diameter")
        assert la is not None
        assert la.value in (25, "25")
        assert "19-40" in (la.reference_range or "")

        # Left Ventricular ED Dimension
        lvedd = meas_map.get("Left Ventricular ED Dimension")
        assert lvedd is not None
        assert lvedd.value in (42, "42")
        assert "33-55" in (lvedd.reference_range or "")

        # Left Ventricular ES Dimension
        lvesd = meas_map.get("Left Ventricular ES Dimension")
        assert lvesd is not None
        assert lvesd.value in (25, "25")
        assert "22-40" in (lvesd.reference_range or "")

        # Inter Vent. Septum thickness D
        ivs = meas_map.get("Inter Vent. Septum thickness D")
        assert ivs is not None
        assert ivs.value in (13, "13")
        assert "06-11" in (ivs.reference_range or "")

        # LVposterior wall thickness D
        lvpw = meas_map.get("LVposterior wall thickness D")
        assert lvpw is not None
        assert lvpw.value in (10, "10")
        assert "06-11" in (lvpw.reference_range or "")

        # Ejection Fraction
        ef = meas_map.get("Ejection Fraction")
        assert ef is not None
        assert ef.value in (60, "60")
        assert ef.unit == "%"
        assert "55-74" in (ef.reference_range or "")

        # Fractional shortening
        fs = meas_map.get("Fractional shortening")
        assert fs is not None
        assert fs.value in (32.5, "32.5")
        assert fs.unit == "%"
        assert "28-40" in (fs.reference_range or "")

        # Aortic Velocity
        av = meas_map.get("Aortic Velocity")
        assert av is not None
        assert av.value in (1.47, "1.47")
        assert av.unit == "m/s"

        # Pulmonary velocity
        pv = meas_map.get("Pulmonary velocity")
        assert pv is not None
        assert pv.value in (1.0, "1.0", 1)
        assert pv.unit == "m/s"

        # PASP
        pasp = meas_map.get("PASP")
        assert pasp is not None
        assert pasp.value in (34, "34")
        assert pasp.unit == "mmHg"

    # -----------------------------------------------------------------------
    # Criterion 5: Normalized Concepts
    # -----------------------------------------------------------------------
    def test_05_normalized_concepts_presence(self):
        concepts_by_orig = {c["original_text"]: c for c in self.concepts}

        assert concepts_by_orig["Conc LVH"]["concept"] == "Concentric Left Ventricular Hypertrophy"
        assert concepts_by_orig["No RWMA"]["concept"] == "Regional Wall Motion Abnormality"
        assert concepts_by_orig["normal LV function"]["concept"] == "Normal Left Ventricular Function"
        assert concepts_by_orig["Grade 1 LVDD"]["concept"] == "Grade 1 Left Ventricular Diastolic Dysfunction"
        assert concepts_by_orig["Mild TR"]["concept"] == "Mild Tricuspid Regurgitation"
        assert concepts_by_orig["Normal RV function"]["concept"] == "Normal Right Ventricular Function"
        assert concepts_by_orig["No Aortic regurgitation"]["concept"] == "Aortic Regurgitation"
        assert concepts_by_orig["No Pulmonary regurgitation present"]["concept"] == "Pulmonary Regurgitation"
        assert concepts_by_orig["No effusion"]["concept"] == "Pericardial Effusion"
        assert concepts_by_orig["No LA/LV clot"]["concept"] == "Thrombus"
        assert concepts_by_orig["No gradient across LVOT"]["concept"] == "Left Ventricular Outflow Tract Gradient"
        assert concepts_by_orig["IAS/IVS intact"]["concept"] == "Intact Interatrial and Interventricular Septa"

    # -----------------------------------------------------------------------
    # Criterion 6: Semantic Categories
    # -----------------------------------------------------------------------
    def test_06_semantic_categories_controlled(self):
        for c in self.concepts:
            cat = c.get("semantic_category")
            assert cat is not None
            assert cat in SemanticCategory.ALL, f"Invalid semantic category '{cat}' for concept '{c['concept']}'"

        concepts_by_orig = {c["original_text"]: c for c in self.concepts}

        assert concepts_by_orig["Conc LVH"]["semantic_category"] == SemanticCategory.STRUCTURAL_FINDING
        assert concepts_by_orig["No RWMA"]["semantic_category"] == SemanticCategory.WALL_MOTION
        assert concepts_by_orig["normal LV function"]["semantic_category"] == SemanticCategory.FUNCTION
        assert concepts_by_orig["Normal RV function"]["semantic_category"] == SemanticCategory.FUNCTION
        assert concepts_by_orig["Grade 1 LVDD"]["semantic_category"] == SemanticCategory.DIASTOLIC_FUNCTION
        assert concepts_by_orig["Mild TR"]["semantic_category"] == SemanticCategory.VALVULAR_FINDING
        assert concepts_by_orig["No Aortic regurgitation"]["semantic_category"] == SemanticCategory.VALVULAR_FINDING
        assert concepts_by_orig["No Pulmonary regurgitation present"]["semantic_category"] == SemanticCategory.VALVULAR_FINDING
        assert concepts_by_orig["No effusion"]["semantic_category"] == SemanticCategory.EFFUSION
        assert concepts_by_orig["No LA/LV clot"]["semantic_category"] == SemanticCategory.THROMBUS
        assert concepts_by_orig["No gradient across LVOT"]["semantic_category"] == SemanticCategory.DOPPLER_MEASUREMENT
        assert concepts_by_orig["IAS/IVS intact"]["semantic_category"] == SemanticCategory.STRUCTURAL_FINDING

        # Measurements
        assert concepts_by_orig["Ejection Fraction"]["semantic_category"] == SemanticCategory.FUNCTION
        assert concepts_by_orig["Fractional shortening"]["semantic_category"] == SemanticCategory.FUNCTION
        assert concepts_by_orig["PASP"]["semantic_category"] == SemanticCategory.PRESSURE
        assert concepts_by_orig["Aortic Velocity"]["semantic_category"] == SemanticCategory.DOPPLER_MEASUREMENT
        assert concepts_by_orig["Pulmonary velocity"]["semantic_category"] == SemanticCategory.DOPPLER_MEASUREMENT
        assert concepts_by_orig["Aortic root diameter"]["semantic_category"] == SemanticCategory.MEASUREMENT

    # -----------------------------------------------------------------------
    # Criterion 7: Relationships & Related Anatomy
    # -----------------------------------------------------------------------
    def test_07_relationships_and_related_anatomy(self):
        concepts_by_orig = {c["original_text"]: c for c in self.concepts}

        # LV findings relate to Left Ventricle
        assert "Left Ventricle" in concepts_by_orig["Conc LVH"]["related_anatomy"]
        assert "Left Ventricle" in concepts_by_orig["No RWMA"]["related_anatomy"]
        assert "Left Ventricle" in concepts_by_orig["normal LV function"]["related_anatomy"]
        assert "Left Ventricle" in concepts_by_orig["Grade 1 LVDD"]["related_anatomy"]
        assert "Left Ventricle" in concepts_by_orig["Ejection Fraction"]["related_anatomy"]
        assert "Left Ventricle" in concepts_by_orig["Fractional shortening"]["related_anatomy"]

        # RV finding relates to Right Ventricle
        assert "Right Ventricle" in concepts_by_orig["Normal RV function"]["related_anatomy"]

        # Valves
        assert "Tricuspid Valve" in concepts_by_orig["Mild TR"]["related_anatomy"]
        assert "Aortic Valve" in concepts_by_orig["No Aortic regurgitation"]["related_anatomy"]
        assert "Pulmonary Valve" in concepts_by_orig["No Pulmonary regurgitation present"]["related_anatomy"]

        # Pericardium
        assert "Pericardium" in concepts_by_orig["No effusion"]["related_anatomy"]

        # Multi-target anatomy: clot relates to Left Atrium AND Left Ventricle
        clot_anat = concepts_by_orig["No LA/LV clot"]["related_anatomy"]
        assert "Left Atrium" in clot_anat
        assert "Left Ventricle" in clot_anat

        # Septum intact relates to Interatrial Septum AND Interventricular Septum
        sept_anat = concepts_by_orig["IAS/IVS intact"]["related_anatomy"]
        assert "Interatrial Septum" in sept_anat
        assert "Interventricular Septum" in sept_anat

        # Outflow tract
        lvot_anat = concepts_by_orig["No gradient across LVOT"]["related_anatomy"]
        assert "Left Ventricular Outflow Tract" in lvot_anat

        # PASP & velocity
        assert "Pulmonary Artery" in concepts_by_orig["PASP"]["related_anatomy"]
        assert "Pulmonary Artery" in concepts_by_orig["Pulmonary velocity"]["related_anatomy"]
        assert "Aorta" in concepts_by_orig["Aortic Velocity"]["related_anatomy"]

    # -----------------------------------------------------------------------
    # Criterion 8: Provenance Preservation
    # -----------------------------------------------------------------------
    def test_08_provenance_preservation(self):
        for c in self.concepts:
            prov = c.get("provenance")
            assert prov is not None
            assert "page" in prov and prov["page"] in (1, 2)
            assert "source_section" in prov and prov["source_section"] is not None
            assert "source_text" in prov and prov["source_text"] is not None
            assert "normalization_source" in prov

    # -----------------------------------------------------------------------
    # Criterion 9: Ambiguity Preservation
    # -----------------------------------------------------------------------
    def test_09_ambiguity_preservation(self):
        # Known unambiguous term in context
        res_lvh = resolve_term("LVH", report_type="echocardiography")
        assert res_lvh.ambiguity is False
        assert res_lvh.ambiguity_status == AmbiguityStatus.RESOLVED

        # Ambiguous term without context must NOT guess
        res_ra_no_ctx = resolve_term("RA")
        assert res_ra_no_ctx.ambiguity is True
        assert res_ra_no_ctx.ambiguity_status == AmbiguityStatus.AMBIGUOUS
        assert res_ra_no_ctx.normalized is None
        assert "Right Atrium" in res_ra_no_ctx.candidates
        assert "Rheumatoid Arthritis" in res_ra_no_ctx.candidates

        # Unknown term must NOT guess
        res_unknown = resolve_term("XYZ_NONEXISTENT_ABBR")
        assert res_unknown.normalized is None
        assert res_unknown.ambiguity_status == AmbiguityStatus.UNKNOWN

    # -----------------------------------------------------------------------
    # Criterion 10: No Clinical Interpretation Introduced
    # -----------------------------------------------------------------------
    def test_10_no_clinical_interpretation(self):
        forbidden_keys = {
            "interpretation",
            "is_abnormal",
            "abnormal",
            "severity_assessment",
            "clinical_concern",
            "prognosis",
            "danger_level",
            "health_status",
            "diagnostic_inference",
        }
        for c in self.concepts:
            for k in forbidden_keys:
                assert k not in c, f"Forbidden interpretation key '{k}' found in concept record"

        # Check raw report.json serialization as well
        ci_dict = self.ci.to_dict()
        ci_json_str = json.dumps(ci_dict).lower()
        assert "enlarged heart" not in ci_json_str
        assert "dangerous" not in ci_json_str
        assert "increased cardiovascular risk" not in ci_json_str
        assert "healthy heart" not in ci_json_str
        assert "pulmonary hypertension" not in ci_json_str

    # -----------------------------------------------------------------------
    # Criterion 11: Original Text Preserved Verbatim
    # -----------------------------------------------------------------------
    def test_11_original_text_preserved(self):
        for c in self.concepts:
            assert "original_text" in c
            assert c["original_text"], "original_text must not be empty"

        # Verify exact surface forms
        orig_texts = {c["original_text"] for c in self.concepts}
        assert "Conc LVH" in orig_texts
        assert "No RWMA" in orig_texts
        assert "Grade 1 LVDD" in orig_texts
        assert "Mild TR" in orig_texts
        assert "IAS/IVS intact" in orig_texts
        assert "No gradient across LVOT" in orig_texts

    # -----------------------------------------------------------------------
    # Criterion 12: Phase 3 Non-Regression
    # -----------------------------------------------------------------------
    def test_12_phase3_non_regression(self):
        assert len(self.ci.findings) >= 15
        assert len(self.ci.measurements) == 11
        assert len(self.ci.anatomy) >= 10
        assert len(self.ci.relationships) >= 20

    # -----------------------------------------------------------------------
    # Critical Context Collision: "EF 60%" vs "Normal 'EF' slope"
    # -----------------------------------------------------------------------
    def test_context_collision_ef_vs_ef_slope(self):
        """
        'Ejection Fraction: 60%' and 'Normal 'EF' slope' must NEVER collapse
        into the same concept.
        """
        concepts_by_orig = {c["original_text"]: c for c in self.concepts}

        # Measurement EF
        ef_meas = concepts_by_orig.get("Ejection Fraction")
        assert ef_meas is not None
        assert ef_meas["concept"] == "Ejection Fraction"
        assert ef_meas["type"] == EntityType.MEASUREMENT
        assert ef_meas["semantic_category"] == SemanticCategory.FUNCTION
        assert "Left Ventricle" in ef_meas["related_anatomy"]
        assert ef_meas["value"] in (60, "60")
        assert ef_meas["unit"] == "%"

        # Observation EF slope
        # Surface text in report is "Normal ‘EF’ slope"
        ef_slope = next((c for c in self.concepts if "slope" in c["original_text"].lower()), None)
        assert ef_slope is not None
        assert ef_slope["concept"] != "Ejection Fraction", "EF slope incorrectly collapsed to Ejection Fraction!"
        assert "Pulmonary Valve" in ef_slope["concept"] or "Slope" in ef_slope["concept"]
        assert ef_slope["type"] == EntityType.FINDING
        assert ef_slope["semantic_category"] == SemanticCategory.VALVULAR_FINDING
        assert "Pulmonary Valve" in ef_slope["related_anatomy"]
        assert ef_slope["assertion"] == AssertionStatus.NORMAL

        # Direct resolver test
        res_ef = resolve_term("EF", report_type="echocardiography")
        res_slope = resolve_term("Normal 'EF' slope", report_type="echocardiography")
        assert res_ef.normalized == "Ejection Fraction"
        assert res_slope.normalized == "Normal Pulmonary Valve EF Slope"
        assert res_ef.normalized != res_slope.normalized

    # -----------------------------------------------------------------------
    # Phase 5 Output Contract Verification
    # -----------------------------------------------------------------------
    def test_phase5_contract_structure(self):
        """Verify each concept matches the precise Phase 4 -> Phase 5 contract."""
        required_keys = {
            "concept",
            "original_text",
            "type",
            "semantic_category",
            "value",
            "unit",
            "reference_range",
            "assertion",
            "modifiers",
            "related_anatomy",
            "provenance",
        }
        for c in self.concepts:
            assert required_keys.issubset(c.keys()), f"Missing keys in concept record: {set(c.keys()) ^ required_keys}"
            assert isinstance(c["modifiers"], dict)
            assert isinstance(c["related_anatomy"], list)
            assert isinstance(c["provenance"], dict)
            assert "source_text" in c["provenance"]
            assert "source_section" in c["provenance"]
            assert "page" in c["provenance"]
