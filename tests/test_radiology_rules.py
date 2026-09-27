"""
tests/test_radiology_rules.py

Unit tests for RadiologyRules (CT, MRI, X-ray, Ultrasound).
Covers:
- Anatomy extraction across thoracic, abdominal, spine, and chest X-ray
- Finding extraction with correct assertion (PRESENT / ABSENT) from negated sentences
- Inline numeric measurement extraction (~ prefix and glued unit suffixes)
- Tabular MRI spinal canal measurement extraction (Level / mm pairs)
- Absence of fabricated reference ranges (strictly None)
"""

from __future__ import annotations

from clinical_extraction.models import AssertionStatus
from clinical_extraction.report_rules.radiology import RadiologyRules


class MockSection:
    def __init__(self, title: str, text: str, page: int = 1):
        self.title = title
        self.text = text
        self.page = page


def test_radiology_rules_metadata():
    rules = RadiologyRules()
    assert rules.report_type == "radiology"
    assert len(rules.ANATOMY_PATTERNS) > 0
    assert len(rules.FINDING_PATTERNS) > 0


def test_radiology_anatomy_extraction():
    rules = RadiologyRules()
    sections = [
        MockSection(
            "Thorax",
            "Trachea is midline. Right and left main bronchi are clear. "
            "Lungs & Pleura show no abnormality. Mediastinum and chest wall are intact. Axilla is unremarkable.",
        ),
        MockSection(
            "Abdomen",
            "Liver is enlarged. Gall bladder is well distended. Proximal CBD is normal in caliber. "
            "Pancreas, spleen, right kidney, left kidney, urinary bladder, and prostate are evaluated.",
        ),
        MockSection(
            "Spine",
            "Cervical vertebrae reveal normal alignment. Intervertebral disc shows normal signal. "
            "Facet joints are unremarkable. Spinal cord and cauda equina appear normal. Sacroiliac joint is intact.",
        ),
        MockSection(
            "Chest X-Ray",
            "Both domes of diaphragm appear normal. CP angles are clear. Hila appear normal.",
        ),
    ]

    anatomy = rules.extract_anatomy(sections)
    extracted_texts = {a.text.lower() for a in anatomy}

    # Thoracic
    assert "trachea" in extracted_texts
    assert "bronchi" in extracted_texts or "bronchus" in extracted_texts
    assert "lungs" in extracted_texts or "lung" in extracted_texts
    assert "pleura" in extracted_texts
    assert "mediastinum" in extracted_texts
    assert "chest wall" in extracted_texts
    assert "axilla" in extracted_texts

    # Abdominal
    assert "liver" in extracted_texts
    assert "gall bladder" in extracted_texts or "gallbladder" in extracted_texts
    assert "cbd" in extracted_texts
    assert "pancreas" in extracted_texts
    assert "spleen" in extracted_texts
    assert "right kidney" in extracted_texts or "kidney" in extracted_texts
    assert "left kidney" in extracted_texts or "kidneys" in extracted_texts
    assert "urinary bladder" in extracted_texts or "bladder" in extracted_texts
    assert "prostate" in extracted_texts

    # Spine
    assert "vertebrae" in extracted_texts or "vertebra" in extracted_texts
    assert "intervertebral disc" in extracted_texts
    assert "facet joints" in extracted_texts
    assert "spinal cord" in extracted_texts or "cord" in extracted_texts
    assert "cauda equina" in extracted_texts
    assert "sacroiliac joint" in extracted_texts

    # Chest X-Ray
    assert "diaphragm" in extracted_texts
    assert "cp angles" in extracted_texts or "cp angle" in extracted_texts or "costophrenic angle" in extracted_texts
    assert "hila" in extracted_texts


def test_radiology_finding_extraction_and_assertion():
    rules = RadiologyRules()
    sections = [
        MockSection(
            "CT Findings",
            "Large right sided pneumothorax is seen with mild pleural effusion. "
            "No pleural thickening is seen. "
            "No abnormal mediastinal lymphadenopathy is seen.",
        ),
        MockSection(
            "MRI Observations",
            "The cervical vertebrae reveal normal signal intensity and alignment. "
            "No disc bulge is noted. "
            "The facet joints are unremarkable.",
        ),
        MockSection(
            "USG Findings",
            "Liver shows Grade-II fatty liver. "
            "No intrahepatic biliary dilatation seen. "
            "No calculus or hydronephrosis is seen in either kidney.",
        ),
    ]

    findings = rules.extract_findings(sections)
    findings_map = {f.text.lower(): f for f in findings}

    # Present findings
    pneumo = next((f for t, f in findings_map.items() if "pneumothorax" in t), None)
    assert pneumo is not None
    assert pneumo.assertion == AssertionStatus.PRESENT
    assert pneumo.negated is False

    effusion = next((f for t, f in findings_map.items() if "pleural effusion" in t), None)
    assert effusion is not None
    assert effusion.assertion == AssertionStatus.PRESENT
    assert effusion.negated is False

    fatty_liver = next((f for t, f in findings_map.items() if "fatty liver" in t), None)
    assert fatty_liver is not None
    assert fatty_liver.assertion == AssertionStatus.PRESENT
    assert fatty_liver.negated is False

    unremarkable = next((f for t, f in findings_map.items() if "unremarkable" in t), None)
    assert unremarkable is not None
    assert unremarkable.negated is False

    # Negated findings
    thickening = next((f for t, f in findings_map.items() if "pleural thickening" in t), None)
    assert thickening is not None
    assert thickening.assertion == AssertionStatus.ABSENT
    assert thickening.negated is True

    bulge = next((f for t, f in findings_map.items() if "disc bulge" in t), None)
    assert bulge is not None
    assert bulge.assertion == AssertionStatus.ABSENT
    assert bulge.negated is True

    lymph = next((f for t, f in findings_map.items() if "lymphadenopathy" in t), None)
    assert lymph is not None
    assert lymph.assertion == AssertionStatus.ABSENT
    assert lymph.negated is True

    dilat = next((f for t, f in findings_map.items() if "dilatation" in t), None)
    assert dilat is not None
    assert dilat.assertion == AssertionStatus.ABSENT
    assert dilat.negated is True

    calculus = next((f for t, f in findings_map.items() if "calculus" in t), None)
    assert calculus is not None
    assert calculus.assertion == AssertionStatus.ABSENT
    assert calculus.negated is True


def test_radiology_inline_measurements():
    rules = RadiologyRules()
    text = (
        "Liver: is enlarged in size (~15.8cm), normal in outline.\n"
        "Gall bladder: A large echogenic calculus measuring ~20mm size is seen.\n"
        "Right kidney: is normal in size (~9.1cm).\n"
        "Prostate: is normal in size (Vol~22cc), shape and echotexture."
    )
    sections = [MockSection("Findings", text)]

    measurements = rules.extract_measurements(sections)
    meas_map = {m.name.lower(): m for m in measurements}

    # Liver measurement
    liver_m = next((m for k, m in meas_map.items() if "liver" in k), None)
    assert liver_m is not None
    assert liver_m.value == 15.8
    assert liver_m.unit == "cm"
    assert liver_m.reference_range is None

    # Calculus measurement
    calc_m = next((m for k, m in meas_map.items() if "calculus" in k), None)
    assert calc_m is not None
    assert calc_m.value == 20
    assert calc_m.unit == "mm"
    assert calc_m.reference_range is None

    # Right kidney measurement
    rk_m = next((m for k, m in meas_map.items() if "right kidney" in k or "kidney" in k), None)
    assert rk_m is not None
    assert rk_m.value == 9.1
    assert rk_m.unit == "cm"
    assert rk_m.reference_range is None

    # Prostate volume measurement
    prostate_m = next((m for k, m in meas_map.items() if "prostate" in k or "volume" in k), None)
    assert prostate_m is not None
    assert prostate_m.value == 22
    assert prostate_m.unit == "cc"
    assert prostate_m.reference_range is None


def test_radiology_mri_tabular_measurements():
    rules = RadiologyRules()

    # Markdown table format as produced by PDF parser
    table_text = (
        "The sagittal diameters of the lumbar spinal canal are as follows (in mm):\n\n"
        "|Level :|L1-2|L2-3|L3-4|L4-5|L5-S1|\n"
        "|---|---|---|---|---|---|\n"
        "|(mm):|**15.4**|**14.5**|**13.5**|**12.8**|**13.2**|"
    )
    sections = [MockSection("Observations", table_text)]

    measurements = rules.extract_measurements(sections)
    assert len(measurements) == 5

    expected = {
        "sagittal diameter l1-2": (15.4, "mm"),
        "sagittal diameter l2-3": (14.5, "mm"),
        "sagittal diameter l3-4": (13.5, "mm"),
        "sagittal diameter l4-5": (12.8, "mm"),
        "sagittal diameter l5-s1": (13.2, "mm"),
    }

    for m in measurements:
        k = m.name.lower()
        assert k in expected, f"Unexpected measurement {m.name}"
        exp_val, exp_unit = expected[k]
        assert m.value == exp_val
        assert m.unit == exp_unit
        assert m.reference_range is None


def test_radiology_mri_narrative_table_measurements():
    rules = RadiologyRules()

    # Narrative/inline level-number pair format
    narrative_text = (
        "The sagittal diameters of the lumbar spinal canal are as follows (in mm): "
        "Level: L1-2 L2-3 L3-4 L4-5 L5-S1 / (mm): 15.4 14.5 13.5 12.8 13.2"
    )
    sections = [MockSection("Observations", narrative_text)]

    measurements = rules.extract_measurements(sections)
    assert len(measurements) == 5

    expected_levels = {"l1-2", "l2-3", "l3-4", "l4-5", "l5-s1"}
    found_levels = {m.name.lower().replace("sagittal diameter ", "") for m in measurements}
    assert found_levels == expected_levels

    for m in measurements:
        assert m.unit == "mm"
        assert m.reference_range is None
