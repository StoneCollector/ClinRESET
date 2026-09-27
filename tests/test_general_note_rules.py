"""
tests/test_general_note_rules.py

Unit tests for GeneralNoteRules (general narrative clinical notes).
Covers:
- Anatomy extraction
- Finding extraction with correct assertion (PRESENT / ABSENT) from negated phrases
- Structured vitals / measurement extraction (BP, Pulse, Temp, BMI, SpO2)
- Absence of echo-specific or administrative false positives
"""

from __future__ import annotations

from clinical_extraction.models import AssertionStatus
from clinical_extraction.report_rules.general_note import GeneralNoteRules
from extraction.models import Section


class MockSection:
    def __init__(self, title: str, text: str, page: int = 1):
        self.title = title
        self.text = text
        self.page = page


def test_general_note_rules_metadata():
    rules = GeneralNoteRules()
    assert rules.report_type == "general_clinical_note"
    assert len(rules.ANATOMY_PATTERNS) > 0
    assert len(rules.FINDING_PATTERNS) > 0


def test_general_note_anatomy_extraction():
    rules = GeneralNoteRules()
    sections = [
        MockSection(
            "Chief Complaint",
            "Patient complains of severe chest pain radiating to left arm. Also notes mild acne on face.",
        ),
        MockSection(
            "Clinical Observations",
            "Abdomen is soft, non-tender. Pelvis and ovary unremarkable on palpation.",
        ),
    ]

    anatomy = rules.extract_anatomy(sections)
    extracted_texts = {a.text.lower() for a in anatomy}

    assert "chest" in extracted_texts
    assert "face" in extracted_texts
    assert "abdomen" in extracted_texts
    assert "ovary" in extracted_texts


def test_general_note_finding_extraction_and_assertion():
    rules = GeneralNoteRules()
    text = (
        "Complains of irregular menstrual cycles and recent weight gain. "
        "Mild acne on face, no hirsutism. "
        "No chest pain or shortness of breath. "
        "Preliminary Diagnosis: Polycystic Ovary Syndrome (PCOS)."
    )
    sections = [MockSection("Clinical Observations", text)]

    findings = rules.extract_findings(sections)
    findings_map = {f.text.lower(): f for f in findings}

    # Verify present finding: acne
    acne_finding = next((f for t, f in findings_map.items() if "acne" in t), None)
    assert acne_finding is not None
    assert acne_finding.assertion == AssertionStatus.PRESENT
    assert acne_finding.negated is False

    # Verify negated finding: no hirsutism
    hirsutism_finding = next((f for t, f in findings_map.items() if "hirsutism" in t), None)
    assert hirsutism_finding is not None
    assert hirsutism_finding.assertion == AssertionStatus.ABSENT
    assert hirsutism_finding.negated is True

    # Verify present diagnosis / symptom
    pcos_finding = next((f for t, f in findings_map.items() if "pcos" in t or "polycystic" in t), None)
    assert pcos_finding is not None
    assert pcos_finding.assertion == AssertionStatus.PRESENT
    assert pcos_finding.negated is False

    # Verify irregular menstrual cycles
    cycle_finding = next((f for t, f in findings_map.items() if "irregular menstrual" in t), None)
    assert cycle_finding is not None
    assert cycle_finding.assertion == AssertionStatus.PRESENT

    # Verify negated chest pain
    cp_finding = next((f for t, f in findings_map.items() if "chest pain" in t), None)
    assert cp_finding is not None
    assert cp_finding.assertion == AssertionStatus.ABSENT
    assert cp_finding.negated is True


def test_general_note_vitals_measurement_extraction():
    rules = GeneralNoteRules()
    text = (
        "Patient: Jane Doe, Age: 28, Gender: Female\n"
        "Vitals: BP 118/76 mmHg, Pulse 82 bpm, Temp 98.6 F. BMI: 29.1.\n"
        "Oxygen saturation: 98% on room air."
    )
    sections = [MockSection("Clinical Observations", text)]

    measurements = rules.extract_measurements(sections=sections)
    meas_map = {m.name.lower(): m for m in measurements}

    # Check Blood Pressure
    bp = next((m for k, m in meas_map.items() if "blood pressure" in k or "bp" in k), None)
    assert bp is not None
    assert bp.value == "118/76"
    assert bp.unit == "mmHg"
    assert bp.reference_range is None

    # Check Pulse
    pulse = next((m for k, m in meas_map.items() if "pulse" in k or "heart rate" in k), None)
    assert pulse is not None
    assert pulse.value == 82
    assert pulse.unit == "bpm"

    # Check Temperature
    temp = next((m for k, m in meas_map.items() if "temp" in k), None)
    assert temp is not None
    assert temp.value == 98.6

    # Check BMI
    bmi = next((m for k, m in meas_map.items() if "bmi" in k), None)
    assert bmi is not None
    assert bmi.value == 29.1

    # Check SpO2
    spo2 = next((m for k, m in meas_map.items() if "oxygen saturation" in k or "spo2" in k), None)
    assert spo2 is not None
    assert spo2.value == 98
    assert spo2.unit == "%"

    # Administrative terms like "Age: 28" must NOT be extracted as measurements
    assert not any("age" in m.name.lower() for m in measurements)
    assert not any("jane doe" in m.name.lower() for m in measurements)
