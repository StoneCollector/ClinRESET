"""
tests/test_classifier.py

Test suite for the Phase 2 rule-based report type classifier.

Test scenarios
--------------
1.  Real echocardiography report (from existing sample_report.json /
    sample_report.pdf) — verifies CONFIDENT classification and correct
    evidence items.
2.  No document title but characteristic echo terminology present —
    verifies that the classifier can identify a report type from
    section/measurement signals alone.
3.  Generic medical terminology that belongs to a different report type
    (CBC) — verifies that echo-specific terms outweigh generic ones when
    the document is a CBC.
4.  Ambiguous / insufficient document — verifies that AMBIGUOUS or
    UNKNOWN is returned rather than a forced classification.
5.  Unknown report type — verifies that UNKNOWN is returned for documents
    with no matching vocabulary.

Synthetic test documents
------------------------
All ExtractionResult objects constructed in this file that are NOT
derived from the real sample PDF are clearly marked as SYNTHETIC.
They are not real clinical documents and must not be treated as
clinical ground truth.  They exist only to exercise classifier logic.

DO NOT modify Phase 1 tests or Phase 1 behaviour to make these pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from extraction.models import (
    ExtractionResult,
    DocumentMeta,
    Section,
    Table,
    TableRow,
    Measurement,
    RawOutput,
    ValidationResult,
)
from classification.classifier import classify, MIN_VIABLE_SCORE, CONFIDENCE_THRESHOLD
from classification.models import ClassificationResult
from classification.signal_extractor import extract_signals, _strip_markup
from classification.signatures import ECHOCARDIOGRAPHY, CBC, ALL_SIGNATURES


# ---------------------------------------------------------------------------
# Helpers — synthetic document builders
# ---------------------------------------------------------------------------


def _make_doc_meta(name: str = "test_report.pdf") -> DocumentMeta:
    return DocumentMeta(
        file_name=name,
        page_count=1,
        source_type="digital_pdf",
        extractor="pymupdf4llm",
    )


def _make_validation(status: str = "GOOD") -> ValidationResult:
    return ValidationResult(status=status, warnings=[], scores={"_aggregate": 1.0})


# ---------------------------------------------------------------------------
# Test 1: Real echocardiography report
# ---------------------------------------------------------------------------


class TestRealEchoReport:
    """
    Verifies classifier behaviour on the real extracted echocardiography
    report.  Uses the existing output/sample_report/normalized/report.json
    to avoid re-running Phase 1.

    This test is skipped if the pre-computed report.json is absent so that
    it does not block CI environments that have not yet run extraction.
    """

    REPORT_JSON = (
        Path(__file__).parent.parent
        / "output"
        / "sample_report"
        / "normalized"
        / "report.json"
    )

    @pytest.fixture(autouse=True)
    def _load_report(self):
        if not self.REPORT_JSON.exists():
            pytest.skip(f"report.json not found: {self.REPORT_JSON}")
        raw = json.loads(self.REPORT_JSON.read_text(encoding="utf-8"))
        # Reconstruct a minimal ExtractionResult from the JSON.
        doc = raw["document"]
        self.result = ExtractionResult(
            document=DocumentMeta(
                file_name=doc["file_name"],
                page_count=doc["page_count"],
                source_type=doc["source_type"],
                extractor=doc["extractor"],
            ),
            sections=[
                Section(
                    title=s["title"],
                    page=s["page"],
                    text=s["text"],
                    table_refs=s.get("table_refs", []),
                )
                for s in raw.get("sections", [])
            ],
            tables=[
                Table(
                    title=t["title"],
                    page=t["page"],
                    headers=t.get("headers", []),
                    rows=[
                        TableRow(
                            name=r["name"],
                            value=r["value"],
                            unit=r.get("unit"),
                            reference_range=r.get("reference_range"),
                        )
                        for r in t.get("rows", [])
                    ],
                    raw_rows=t.get("raw_rows", []),
                )
                for t in raw.get("tables", [])
            ],
            measurements=[
                Measurement(
                    name=m["name"],
                    value=m["value"],
                    unit=m.get("unit"),
                    reference_range=m.get("reference_range"),
                    page=m.get("page"),
                    source_section=m.get("source_section"),
                )
                for m in raw.get("measurements", [])
            ],
            raw=RawOutput(
                text=raw.get("raw", {}).get("text", ""),
                markdown=raw.get("raw", {}).get("markdown", ""),
            ),
            validation=ValidationResult(
                status=raw["validation"]["status"],
                warnings=raw["validation"].get("warnings", []),
                scores=raw["validation"].get("scores", {}),
            ),
        )
        self.classification = classify(self.result)

    # --- Core result checks ---

    def test_classified_as_echocardiography(self):
        assert self.classification.report_type == "echocardiography", (
            f"Expected 'echocardiography', got '{self.classification.report_type}'. "
            f"Status: {self.classification.status}, "
            f"Confidence: {self.classification.confidence:.3f}"
        )

    def test_status_is_confident(self):
        assert self.classification.status == "CONFIDENT", (
            f"Expected CONFIDENT, got {self.classification.status}"
        )

    def test_confidence_is_high(self):
        assert self.classification.confidence >= 0.70, (
            f"Confidence too low: {self.classification.confidence:.3f}"
        )

    def test_evidence_is_not_empty(self):
        assert len(self.classification.evidence) > 0, "No evidence recorded"

    # --- Evidence signal checks ---

    def test_evidence_contains_echo_cardiography_report(self):
        """ECHO CARDIOGRAPHY REPORT must appear as a title-level match."""
        matched_texts = [e.signal_text.upper() for e in self.classification.evidence]
        assert any("ECHO CARDIOGRAPHY" in t for t in matched_texts), (
            "No evidence item contains 'ECHO CARDIOGRAPHY'. Evidence:\n"
            + "\n".join(str(e) for e in self.classification.evidence)
        )

    def test_evidence_contains_m_mode_parameters(self):
        """M-MODE PARAMETERS section must contribute to evidence."""
        matched = [e for e in self.classification.evidence
                   if "M-MODE" in e.signal_text.upper() or "M MODE" in e.signal_text.upper()]
        assert matched, (
            "No evidence item references M-MODE PARAMETERS. Evidence:\n"
            + "\n".join(str(e) for e in self.classification.evidence)
        )

    def test_evidence_contains_ejection_fraction(self):
        """Ejection Fraction must contribute as a measurement or keyword signal."""
        matched = [e for e in self.classification.evidence
                   if "EJECTION FRACTION" in e.signal_text.upper()
                   or (e.matched_pattern and "Ejection Fraction" in e.matched_pattern)]
        assert matched, (
            "No evidence item references Ejection Fraction. Evidence:\n"
            + "\n".join(str(e) for e in self.classification.evidence)
        )

    def test_evidence_contains_doppler(self):
        """Doppler keyword must be found somewhere in the evidence."""
        matched = [e for e in self.classification.evidence
                   if "DOPPLER" in e.signal_text.upper()
                   or (e.matched_pattern and "Doppler" in e.matched_pattern)]
        assert matched, (
            "No Doppler evidence found. Evidence:\n"
            + "\n".join(str(e) for e in self.classification.evidence)
        )

    def test_evidence_contains_lv_rv_terminology(self):
        """LV or RV terminology must appear in evidence."""
        lv_rv_patterns = {"LV", "RV", "LEFT VENTRICLE", "RIGHT VENTRICLE"}
        matched = [
            e for e in self.classification.evidence
            if any(p in e.signal_text.upper() for p in lv_rv_patterns)
        ]
        assert matched, "No LV/RV evidence found"

    def test_evidence_contains_pasp(self):
        """PASP must appear in evidence (from FINAL IMPRESSION section)."""
        matched = [e for e in self.classification.evidence
                   if "PASP" in e.signal_text.upper()
                   or (e.matched_pattern and "PASP" in e.matched_pattern)]
        assert matched, "PASP not found in evidence"

    def test_evidence_contains_lvh_rwma_or_lvdd(self):
        """LVH, RWMA, or LVDD must appear in evidence."""
        keywords = {"LVH", "RWMA", "LVDD"}
        matched = [
            e for e in self.classification.evidence
            if any(kw in e.signal_text.upper() for kw in keywords)
        ]
        assert matched, "None of LVH / RWMA / LVDD found in evidence"

    # --- Evidence traceability ---

    def test_evidence_items_have_source_field(self):
        for e in self.classification.evidence:
            assert e.source_field, f"Evidence item missing source_field: {e}"

    def test_evidence_items_have_signal_category(self):
        for e in self.classification.evidence:
            assert e.signal_category, f"Evidence item missing signal_category: {e}"

    def test_evidence_items_have_matched_pattern(self):
        for e in self.classification.evidence:
            assert e.matched_pattern is not None, (
                f"Evidence item missing matched_pattern: {e}"
            )

    def test_evidence_has_title_match(self):
        """At least one evidence item must be a title-level match."""
        title_matches = [e for e in self.classification.evidence
                         if e.signal_category == "title_match"]
        assert title_matches, "No title_match evidence found"

    def test_title_match_has_highest_weight(self):
        """The title match should carry the highest weight of all evidence."""
        if not self.classification.evidence:
            pytest.skip("No evidence to check")
        title_evidence = [e for e in self.classification.evidence
                          if e.signal_category == "title_match"]
        if not title_evidence:
            pytest.skip("No title evidence to check weight")
        max_title_weight = max(e.weight for e in title_evidence)
        max_any_weight = max(e.weight for e in self.classification.evidence)
        assert max_title_weight == max_any_weight, (
            f"Title match weight ({max_title_weight}) is not the highest "
            f"(max weight: {max_any_weight})"
        )

    # --- Serialisation ---

    def test_to_dict_contains_classification(self):
        """report.json to_dict() must include a classification section."""
        self.result.classification = self.classification
        d = self.result.to_dict()
        assert "classification" in d, "classification key missing from to_dict()"
        c = d["classification"]
        assert c["report_type"] == "echocardiography"
        assert "confidence" in c
        assert "status" in c
        assert "evidence" in c
        assert isinstance(c["evidence"], list)
        assert "alternatives" in c

    def test_to_dict_preserves_extraction_fields(self):
        """Existing extraction fields must not be removed by Phase 2."""
        self.result.classification = self.classification
        d = self.result.to_dict()
        for key in ("document", "sections", "tables", "measurements", "raw", "validation"):
            assert key in d, f"Extraction field '{key}' missing from to_dict()"

    def test_classification_serialises_to_json(self):
        """ClassificationResult.to_dict() must produce valid JSON."""
        d = self.classification.to_dict()
        s = json.dumps(d)  # must not raise
        parsed = json.loads(s)
        assert parsed["report_type"] == "echocardiography"


# ---------------------------------------------------------------------------
# Test 2: No document title — only medical terminology present
#         (SYNTHETIC document)
# ---------------------------------------------------------------------------


class TestNoTitleEchoTerminology:
    """
    SYNTHETIC TEST: Verifies that the classifier can identify an
    echocardiography report when the document title is absent,
    relying only on section headings, table headings, and measurements.
    """

    @pytest.fixture(autouse=True)
    def _build_result(self):
        # Deliberately omit the title section; retain characteristic echo content.
        self.result = ExtractionResult(
            document=_make_doc_meta("synthetic_no_title.pdf"),
            sections=[
                Section(title=None, page=1, text="Patient details redacted."),
                Section(title="M-MODE PARAMETERS", page=1, text="Measurements follow."),
                Section(
                    title="ON INTERROGATING WITH PULSE & CONTINUOUS WAVE DOPPLER",
                    page=2,
                    text="No Aortic regurgitation. Pulmonary velocity = 1.0m/s",
                ),
                Section(
                    title="FINAL IMPRESSION",
                    page=2,
                    text="Conc LVH, No RWMA. EF 60% normal LV function. Grade 1 LVDD.",
                ),
            ],
            tables=[
                Table(
                    title="M-MODE PARAMETERS",
                    page=1,
                    headers=["MEASUREMENTS", "", "NORMAL VALUES"],
                    rows=[
                        TableRow(name="Ejection Fraction", value="60", unit="%",
                                 reference_range="(55-74%)"),
                        TableRow(name="Fractional shortening", value="32.5", unit="%",
                                 reference_range="(28-40%)"),
                    ],
                    raw_rows=[],
                )
            ],
            measurements=[
                Measurement(name="Ejection Fraction", value="60", unit="%",
                            reference_range="(55-74%)", page=1),
                Measurement(name="Fractional shortening", value="32.5", unit="%",
                            reference_range="(28-40%)", page=1),
            ],
            raw=RawOutput(
                text="M-MODE PARAMETERS Ejection Fraction 60% Doppler LVH RWMA LVDD PASP",
                markdown="",
            ),
            validation=_make_validation("GOOD"),
        )
        self.classification = classify(self.result)

    def test_classified_as_echocardiography(self):
        assert self.classification.report_type == "echocardiography", (
            f"Expected echocardiography; got {self.classification.report_type}. "
            f"Status={self.classification.status}, confidence={self.classification.confidence:.3f}"
        )

    def test_status_not_unknown(self):
        assert self.classification.status != "UNKNOWN", (
            "Classifier returned UNKNOWN despite characteristic echo terminology"
        )

    def test_evidence_not_empty(self):
        assert self.classification.evidence, "No evidence recorded"

    def test_no_explicit_echo_report_title_match(self):
        """
        Without an explicit 'ECHO CARDIOGRAPHY REPORT' title section,
        the highest-weight title-level evidence should NOT contain the
        canonical echo report title string.

        Note: The signal extractor infers the document title from the first
        meaningful section title present (e.g. 'M-MODE PARAMETERS' here).
        That inferred title may still produce keyword-level matches, which
        is correct and expected.  What this test checks is that a
        full 'ECHO CARDIOGRAPHY REPORT' title match is NOT present,
        because that title was deliberately omitted from this synthetic doc.
        """
        echo_report_title_matches = [
            e for e in self.classification.evidence
            if e.signal_category == "title_match"
            and "ECHO CARDIOGRAPHY REPORT" in e.signal_text.upper()
        ]
        assert not echo_report_title_matches, (
            "A full 'ECHO CARDIOGRAPHY REPORT' title match was found despite "
            "this synthetic document not having that title section.\n"
            "Found: " + str(echo_report_title_matches)
        )

    def test_section_and_measurement_evidence_present(self):
        section_or_measurement = [
            e for e in self.classification.evidence
            if e.source_field in ("section_title", "table_title", "measurement_name",
                                  "section_text", "table_header")
        ]
        assert section_or_measurement, (
            "No section/measurement evidence despite multiple characteristic signals"
        )


# ---------------------------------------------------------------------------
# Test 3: Generic terminology but actually a CBC report
#         (SYNTHETIC document)
# ---------------------------------------------------------------------------


class TestGenericTerminologyCBCReport:
    """
    SYNTHETIC TEST: A CBC report contains some generic medical terminology
    (e.g. 'blood', 'normal') that overlaps superficially with many report
    types.  The classifier must correctly identify it as a CBC, not as
    echocardiography, because CBC-specific signals score higher.
    """

    @pytest.fixture(autouse=True)
    def _build_result(self):
        self.result = ExtractionResult(
            document=_make_doc_meta("synthetic_cbc.pdf"),
            sections=[
                Section(
                    title="COMPLETE BLOOD COUNT",
                    page=1,
                    text="Blood test results follow.",
                ),
                Section(
                    title="HAEMATOLOGY",
                    page=1,
                    text=(
                        "Haemoglobin 13.5 g/dL (12-16). "
                        "WBC 7.2 10^3/uL (4-11). "
                        "Platelet 250 10^3/uL (150-400). "
                        "Normal blood count."
                    ),
                ),
            ],
            tables=[
                Table(
                    title="COMPLETE BLOOD COUNT",
                    page=1,
                    headers=["MEASUREMENT", "VALUE", "NORMAL VALUES"],
                    rows=[
                        TableRow(name="Haemoglobin", value="13.5", unit="g/dL",
                                 reference_range="12-16"),
                        TableRow(name="WBC", value="7.2", unit="10^3/uL",
                                 reference_range="4-11"),
                        TableRow(name="Platelet Count", value="250", unit="10^3/uL",
                                 reference_range="150-400"),
                        TableRow(name="MCV", value="87", unit="fL",
                                 reference_range="80-100"),
                        TableRow(name="MCH", value="29", unit="pg",
                                 reference_range="27-32"),
                        TableRow(name="Neutrophils", value="65", unit="%",
                                 reference_range="40-75"),
                        TableRow(name="Lymphocytes", value="28", unit="%",
                                 reference_range="20-45"),
                    ],
                    raw_rows=[],
                )
            ],
            measurements=[
                Measurement(name="Haemoglobin", value="13.5", unit="g/dL",
                            reference_range="12-16", page=1),
                Measurement(name="WBC", value="7.2", unit="10^3/uL",
                            reference_range="4-11", page=1),
                Measurement(name="Platelet Count", value="250", unit="10^3/uL",
                            reference_range="150-400", page=1),
                Measurement(name="MCV", value="87", unit="fL",
                            reference_range="80-100", page=1),
                Measurement(name="Neutrophils", value="65", unit="%",
                            reference_range="40-75", page=1),
                Measurement(name="Lymphocytes", value="28", unit="%",
                            reference_range="20-45", page=1),
            ],
            raw=RawOutput(
                text=(
                    "COMPLETE BLOOD COUNT\n"
                    "Haemoglobin 13.5 g/dL WBC 7.2 Platelet 250 "
                    "MCV MCH MCHC Differential Count Neutrophils Lymphocytes"
                ),
                markdown="",
            ),
            validation=_make_validation("GOOD"),
        )
        self.classification = classify(self.result)

    def test_classified_as_cbc_not_echo(self):
        assert self.classification.report_type == "cbc", (
            f"Expected 'cbc'; got '{self.classification.report_type}'. "
            f"Status={self.classification.status}, "
            f"confidence={self.classification.confidence:.3f}"
        )

    def test_not_misclassified_as_echo(self):
        assert self.classification.report_type != "echocardiography", (
            "CBC was wrongly classified as echocardiography"
        )

    def test_cbc_evidence_present(self):
        """CBC-specific terms must appear in evidence."""
        cbc_terms = {"haemoglobin", "wbc", "platelet", "neutrophils", "lymphocytes"}
        found = [
            e for e in self.classification.evidence
            if any(t in e.signal_text.lower() for t in cbc_terms)
            or any(t in (e.matched_pattern or "").lower() for t in cbc_terms)
        ]
        assert found, "No CBC-specific evidence items found"


# ---------------------------------------------------------------------------
# Test 4: Ambiguous / insufficient document
#         (SYNTHETIC document)
# ---------------------------------------------------------------------------


class TestAmbiguousDocument:
    """
    SYNTHETIC TEST: A document with very sparse medical content that
    contains overlapping signals from two report types but not enough
    specificity for a confident classification.

    Expected: AMBIGUOUS or UNCERTAIN (not CONFIDENT, not forced).
    """

    @pytest.fixture(autouse=True)
    def _build_result(self):
        # Contains both some echo and some LFT vocabulary, insufficient for either.
        self.result = ExtractionResult(
            document=_make_doc_meta("synthetic_ambiguous.pdf"),
            sections=[
                Section(
                    title=None,
                    page=1,
                    text="Patient report. Doppler study. Bilirubin values noted.",
                ),
            ],
            tables=[],
            measurements=[],
            raw=RawOutput(
                text="Doppler LV Bilirubin SGPT",
                markdown="",
            ),
            validation=_make_validation("DEGRADED"),
        )
        self.classification = classify(self.result)

    def test_not_confident(self):
        assert self.classification.status != "CONFIDENT", (
            "Classifier returned CONFIDENT despite insufficient/ambiguous evidence. "
            f"type={self.classification.report_type}, "
            f"confidence={self.classification.confidence:.3f}"
        )

    def test_result_is_not_forced(self):
        """A low-evidence document must not produce a confident single classification."""
        # Either AMBIGUOUS, UNCERTAIN, or UNKNOWN is acceptable.
        assert self.classification.status in ("AMBIGUOUS", "UNCERTAIN", "UNKNOWN"), (
            f"Unexpected status: {self.classification.status}"
        )

    def test_classification_result_is_valid(self):
        """Result must still be a valid ClassificationResult even for uncertain docs."""
        assert isinstance(self.classification, ClassificationResult)
        assert self.classification.report_type is not None
        assert 0.0 <= self.classification.confidence <= 1.0


# ---------------------------------------------------------------------------
# Test 5: Unknown report type
#         (SYNTHETIC document)
# ---------------------------------------------------------------------------


class TestUnknownReportType:
    """
    SYNTHETIC TEST: A document with no medical vocabulary matching any
    known report type signature.

    Expected: report_type = "unknown", status = "UNKNOWN".
    """

    @pytest.fixture(autouse=True)
    def _build_result(self):
        self.result = ExtractionResult(
            document=_make_doc_meta("synthetic_unknown.pdf"),
            sections=[
                Section(
                    title="ANNUAL PERFORMANCE APPRAISAL",
                    page=1,
                    text=(
                        "Employee has demonstrated exceptional leadership. "
                        "Key performance indicators were met. "
                        "Recommended for promotion."
                    ),
                ),
            ],
            tables=[],
            measurements=[],
            raw=RawOutput(
                text=(
                    "Annual performance appraisal. Leadership skills. "
                    "KPIs met. Promotion recommended."
                ),
                markdown="",
            ),
            validation=_make_validation("GOOD"),
        )
        self.classification = classify(self.result)

    def test_report_type_is_unknown(self):
        assert self.classification.report_type == "unknown", (
            f"Expected 'unknown'; got '{self.classification.report_type}'. "
            f"status={self.classification.status}, "
            f"confidence={self.classification.confidence:.3f}"
        )

    def test_status_is_unknown(self):
        assert self.classification.status == "UNKNOWN", (
            f"Expected UNKNOWN status; got {self.classification.status}"
        )

    def test_confidence_is_low(self):
        assert self.classification.confidence < 0.5, (
            f"Expected low confidence for unknown doc; got {self.classification.confidence:.3f}"
        )

    def test_evidence_is_empty_or_irrelevant(self):
        # For a truly unknown doc, the top-level evidence list may be empty.
        # (Alternatives are populated instead.)
        assert isinstance(self.classification.evidence, list)

    def test_no_clinical_interpretation_in_result(self):
        """
        Classifier must not inject clinical interpretation strings.
        The result may only contain identification fields.
        """
        forbidden = [
            "abnormal", "elevated", "low", "high", "critical",
            "diagnosis", "treat", "recommend",
        ]
        report_text = str(self.classification.to_dict()).lower()
        for word in forbidden:
            # Allow these words if they came from the document itself (evidence),
            # but the report_type and status must not contain them.
            assert word not in self.classification.report_type.lower()
            assert word not in self.classification.status.lower()


# ---------------------------------------------------------------------------
# Unit tests for signal extractor
# ---------------------------------------------------------------------------


class TestSignalExtractor:
    """Unit tests for the signal extraction step."""

    def test_strip_markup_removes_bold(self):
        assert _strip_markup("**ECHO CARDIOGRAPHY REPORT**") == "ECHO CARDIOGRAPHY REPORT"

    def test_strip_markup_removes_html_tags(self):
        assert _strip_markup("<u>M-MODE PARAMETERS</u>") == "M-MODE PARAMETERS"

    def test_strip_markup_removes_heading_markers(self):
        assert _strip_markup("## M-MODE PARAMETERS") == "M-MODE PARAMETERS"

    def test_extract_signals_includes_section_titles(self):
        result = ExtractionResult(
            document=_make_doc_meta(),
            sections=[
                Section(title="ECHO CARDIOGRAPHY REPORT", page=1, text="body"),
                Section(title="M-MODE PARAMETERS", page=1, text=""),
            ],
            validation=_make_validation(),
        )
        signals = extract_signals(result)
        sources = {s.source_field for s in signals}
        assert "section_title" in sources

    def test_extract_signals_includes_measurement_names(self):
        result = ExtractionResult(
            document=_make_doc_meta(),
            measurements=[
                Measurement(name="Ejection Fraction", value="60", unit="%", page=1),
            ],
            validation=_make_validation(),
        )
        signals = extract_signals(result)
        meas_signals = [s for s in signals if s.source_field == "measurement_name"]
        assert any("Ejection Fraction" in s.text for s in meas_signals)

    def test_document_title_inferred_from_first_valid_section(self):
        result = ExtractionResult(
            document=_make_doc_meta(),
            sections=[
                Section(title=None, page=1, text="no title"),
                Section(title="**<u>ECHO CARDIOGRAPHY REPORT</u>**", page=1, text="body"),
            ],
            validation=_make_validation(),
        )
        signals = extract_signals(result)
        doc_title_signals = [s for s in signals if s.source_field == "document_title"]
        assert doc_title_signals, "Expected a document_title signal to be inferred"
        assert "ECHO CARDIOGRAPHY REPORT" in doc_title_signals[0].text

    def test_raw_text_only_added_when_no_structured_signals(self):
        result = ExtractionResult(
            document=_make_doc_meta(),
            raw=RawOutput(text="some raw text", markdown=""),
            validation=_make_validation(),
        )
        signals = extract_signals(result)
        raw_signals = [s for s in signals if s.source_field == "raw_text"]
        # With no sections/tables/measurements, raw_text should be included.
        assert raw_signals, "Expected raw_text signal when no structured content present"

    def test_raw_text_not_added_when_structured_signals_exist(self):
        result = ExtractionResult(
            document=_make_doc_meta(),
            sections=[Section(title="SOME SECTION", page=1, text="body")],
            raw=RawOutput(text="some raw text", markdown=""),
            validation=_make_validation(),
        )
        signals = extract_signals(result)
        raw_signals = [s for s in signals if s.source_field == "raw_text"]
        # Structured signals present → raw_text should NOT be added.
        assert not raw_signals, "raw_text signal should not be added when structured content exists"


# ---------------------------------------------------------------------------
# Unit tests for classifier internals
# ---------------------------------------------------------------------------


class TestClassifierInternals:
    """Tests for classifier scoring and threshold logic."""

    def test_empty_extraction_result_returns_unknown(self):
        """A completely empty ExtractionResult must produce UNKNOWN."""
        result = ExtractionResult(
            document=_make_doc_meta("empty.pdf"),
            sections=[],
            tables=[],
            measurements=[],
            raw=RawOutput(text="", markdown=""),
            validation=_make_validation("FAILED"),
        )
        classification = classify(result)
        assert classification.report_type == "unknown"
        assert classification.status == "UNKNOWN"

    def test_custom_signatures_override_defaults(self):
        """Passing a custom signature list restricts candidate set."""
        result = ExtractionResult(
            document=_make_doc_meta("test.pdf"),
            sections=[
                Section(title="COMPLETE BLOOD COUNT", page=1, text="Haemoglobin 13.5"),
            ],
            measurements=[
                Measurement(name="Haemoglobin", value="13.5", unit="g/dL", page=1),
            ],
            validation=_make_validation("GOOD"),
        )
        # Restrict to only the echocardiography signature.
        classification = classify(result, signatures=[ECHOCARDIOGRAPHY])
        # With only echo signature available, CBC signals won't match →
        # result must be UNKNOWN (echo score too low).
        assert classification.report_type in ("unknown", "echocardiography")
        # If echo, confidence must be low.
        if classification.report_type == "echocardiography":
            assert classification.confidence < 0.5

    def test_classification_result_fields_are_present(self):
        """ClassificationResult must always have all required fields."""
        result = ExtractionResult(
            document=_make_doc_meta(),
            validation=_make_validation(),
        )
        c = classify(result)
        assert hasattr(c, "report_type")
        assert hasattr(c, "confidence")
        assert hasattr(c, "status")
        assert hasattr(c, "evidence")
        assert hasattr(c, "alternatives")

    def test_confidence_is_within_bounds(self):
        """Confidence must always be in [0.0, 1.0]."""
        result = ExtractionResult(
            document=_make_doc_meta(),
            sections=[
                Section(title="ECHO CARDIOGRAPHY REPORT", page=1,
                        text="Ejection Fraction Doppler LVH"),
            ],
            measurements=[
                Measurement(name="Ejection Fraction", value="60", unit="%", page=1),
            ],
            validation=_make_validation(),
        )
        c = classify(result)
        assert 0.0 <= c.confidence <= 1.0

    def test_to_dict_round_trips_through_json(self):
        """ClassificationResult.to_dict() must survive JSON serialisation."""
        result = ExtractionResult(
            document=_make_doc_meta(),
            sections=[
                Section(title="THYROID FUNCTION TEST", page=1,
                        text="TSH 3.5 mIU/L fT4 12 pmol/L"),
            ],
            measurements=[
                Measurement(name="TSH", value="3.5", unit="mIU/L", page=1),
                Measurement(name="fT4", value="12", unit="pmol/L", page=1),
            ],
            validation=_make_validation(),
        )
        c = classify(result)
        d = c.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["report_type"] == c.report_type
        assert parsed["status"] == c.status

    def test_extraction_fields_intact_after_classification(self):
        """
        Phase 1 fields must be fully intact after Phase 2 attaches
        the classification result.
        """
        result = ExtractionResult(
            document=_make_doc_meta("check_intact.pdf"),
            sections=[Section(title="CBC REPORT", page=1, text="WBC 7.2 Haemoglobin 13")],
            measurements=[
                Measurement(name="Haemoglobin", value="13", unit="g/dL", page=1),
            ],
            validation=_make_validation("GOOD"),
        )
        c = classify(result)
        result.classification = c

        d = result.to_dict()
        # Phase 1 fields must still be present.
        assert d["document"]["file_name"] == "check_intact.pdf"
        assert len(d["sections"]) == 1
        assert len(d["measurements"]) == 1
        # Phase 2 field must also be present.
        assert "classification" in d

    def test_no_ml_imports_in_classifier(self):
        """
        Verify that no ML/embedding libraries are imported by the
        classification package.  Catches accidental introductions.
        """
        import sys
        forbidden_modules = {
            "torch", "transformers", "sklearn", "tensorflow",
            "sentence_transformers", "openai", "anthropic",
            "langchain", "chromadb", "faiss",
        }
        import classification.classifier  # noqa: F401
        import classification.signatures  # noqa: F401
        import classification.signal_extractor  # noqa: F401
        loaded = set(sys.modules.keys())
        found = forbidden_modules & loaded
        assert not found, (
            f"Forbidden ML modules found in sys.modules: {found}. "
            "Phase 2 must remain rule-based only."
        )
