import pytest
from src.extraction.rules.measurements import MeasurementParser
from src.extraction.rules.assertions import AssertionClassifier
from src.extraction.rules.rule_extractor import RuleExtractor
from src.segmentation.models import Clause


def test_parse_in_situ_ranges():
    text = "Inter Vent. Septum thickness D 13 (06-11mm)"
    result = MeasurementParser.parse_in_situ_range_measurement(text)
    assert result is not None

    concept, meas = result
    assert "Septum" in concept
    assert meas.value == 13.0
    assert meas.unit == "mm"
    assert meas.reference_range is not None
    assert meas.reference_range.low == 6.0
    assert meas.reference_range.high == 11.0


def test_parse_blood_pressure():
    text = "Vitals: BP 118/76 mmHg, Pulse 82 bpm"
    result = MeasurementParser.parse_blood_pressure(text)
    assert result is not None

    m_sys, m_dia = result
    assert m_sys.value == 118.0
    assert m_sys.unit == "mmHg"
    assert m_dia.value == 76.0
    assert m_dia.unit == "mmHg"


def test_parse_inline_measurements():
    # Echo velocity
    t1 = "Aortic Velocity = 1.47 m/s"
    res1 = MeasurementParser.parse_key_value_measurement(t1)
    assert res1 is not None
    concept1, meas1 = res1
    assert meas1.value == 1.47
    assert meas1.unit == "m/s"

    # Ultrasound liver span
    t2 = "Liver: is enlarged in size (~15.8cm)"
    res2 = MeasurementParser.parse_key_value_measurement(t2)
    assert res2 is not None
    concept2, meas2 = res2
    assert meas2.value == 15.8
    assert meas2.unit == "cm"

    # PASP
    t3 = "Mild TR PASP=34mmHg"
    res3 = MeasurementParser.parse_key_value_measurement(t3)
    assert res3 is not None
    concept3, meas3 = res3
    assert meas3.value == 34.0
    assert meas3.unit == "mmHg"


def test_assertion_classification():
    # Negations -> ABSENT
    assert AssertionClassifier.classify("No focal lesion is seen.") == "ABSENT"
    assert AssertionClassifier.classify("No disc bulge is noted.") == "ABSENT"
    assert AssertionClassifier.classify("MPD is not dilated.") == "ABSENT"
    assert AssertionClassifier.classify("No e/o any calculus / mass seen in its lumen.") == "ABSENT"
    assert AssertionClassifier.classify("no hirsutism") == "ABSENT"
    assert AssertionClassifier.classify("No effusion") == "ABSENT"

    # Normalcy cues -> NORMAL
    assert AssertionClassifier.classify("Lung feilds are clear.") == "NORMAL"
    assert AssertionClassifier.classify("Hila appear normal") == "NORMAL"
    assert AssertionClassifier.classify("The facet joints are unremarkable.") == "NORMAL"
    assert AssertionClassifier.classify("Cardio-thoracic ratio is within normal limits.") == "NORMAL"
    assert AssertionClassifier.classify("IVD Spaces are normal") == "NORMAL"
    assert AssertionClassifier.classify("IAS/IVS intact") == "NORMAL"

    # Findings -> PRESENT
    assert AssertionClassifier.classify("Loss of lumbar lordosis.") == "PRESENT"
    assert AssertionClassifier.classify("Mild acne on face") == "PRESENT"
    assert AssertionClassifier.classify("Large right sided pneumothorax is seen") == "PRESENT"
    assert AssertionClassifier.classify("Grade 1 left ventricular diastolic dysfunction.") == "PRESENT"


def test_rule_extractor_clause():
    clause = Clause(
        clause_id="echo_PA01:p1:s1:c1",
        text="Inter Vent. Septum thickness D 13 (06-11mm)",
        raw_text="Inter Vent. Septum thickness D 13 (06-11mm)",
        page_number=1,
        section_name="M-MODE PARAMETERS",
        source_file="echo_PA01"
    )

    facts = RuleExtractor.extract_from_clause(clause)
    assert len(facts) == 1
    fact = facts[0]
    assert fact.measurement is not None
    assert fact.measurement.value == 13.0
    assert fact.assertion == "PRESENT"  # 13 > 11 => outside range => PRESENT
