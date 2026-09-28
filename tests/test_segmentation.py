import os
from pathlib import Path
import pytest

from src.parsing.parser import PDFParser
from src.segmentation.header_filter import HeaderNoiseFilter
from src.segmentation.clause_splitter import ClauseSplitter
from src.segmentation.segmenter import ReportSegmenter


@pytest.fixture
def parser():
    return PDFParser()


@pytest.fixture
def data_dir():
    cur_dir = Path(__file__).resolve().parent
    return cur_dir.parent / "data"


def test_header_noise_filter_blocks_metadata():
    noise_samples = [
        "Patient Name: Aisha Rahman",
        "NAME: PA01                                                                                DATED:",
        "AGE/SEX: 61y /F                                                                          REF BY: IPD",
        "Age: 28",
        "Gender: Female",
        "Date: 2025-04-08",
        "Physician: Dr. Neha Kapoor",
        "Consultant DM Cardiologist",
        "Consultant MD Radiologist",
        "Please correlate clinically and with other relevant investigations.",
        "Adv: Clinical Correlation",
        "Page 1 of 2",
        "===============================================================",
    ]

    for sample in noise_samples:
        assert HeaderNoiseFilter.is_noise(sample), f"Failed to identify noise: {sample}"


def test_header_noise_filter_retains_clinical_statements():
    clinical_samples = [
        "BP 118/76 mmHg, Pulse 82 bpm",
        "Mild acne on face, no hirsutism",
        "Polycystic Ovary Syndrome (PCOS)",
        "Large right sided pneumothorax is seen",
        "Liver is enlarged in size (~15.8cm), normal in outline.",
        "Loss of lumbar lordosis.",
        "No focal lesion is seen.",
    ]

    for sample in clinical_samples:
        assert not HeaderNoiseFilter.is_noise(sample), f"Incorrectly marked clinical statement as noise: {sample}"


def test_clause_splitter_atomic_boundaries():
    # 1. Decimal preservation
    text1 = "Liver is enlarged in size (~15.8cm), normal in outline."
    clauses1 = ClauseSplitter.split(text1)
    assert len(clauses1) == 2
    assert "15.8cm" in clauses1[0]
    assert "normal in outline" in clauses1[1]

    # 2. Velocity decimal preservation
    text2 = "Aortic Velocity = 1.47 m/s. Pulmonary velocity = 1.0m/s."
    clauses2 = ClauseSplitter.split(text2)
    assert any("1.47 m/s" in c for c in clauses2)
    assert any("1.0m/s" in c for c in clauses2)

    # 3. Contrasting negation boundary
    text3 = "Mild acne on face, no hirsutism"
    clauses3 = ClauseSplitter.split(text3)
    assert "Mild acne on face" in clauses3
    assert "no hirsutism" in clauses3

    # 4. Conc LVH, No RWMA
    text4 = "Conc LVH, No RWMA"
    clauses4 = ClauseSplitter.split(text4)
    assert "Conc LVH" in clauses4
    assert "No RWMA" in clauses4


def test_segment_general_report_no_metadata_leakage(parser, data_dir):
    """
    CRITICAL PHASE 2 CRITERION:
    'Aisha Rahman Age' style garbage is impossible.
    """
    gen_path = data_dir / "general" / "sample Medical Report4.pdf"
    doc = parser.parse(gen_path)
    clauses = ReportSegmenter.segment_document(doc)

    assert len(clauses) > 0

    # Ensure metadata is strictly absent from all clauses
    clause_texts = [c.text for c in clauses]
    for text in clause_texts:
        assert "Aisha" not in text
        assert "Rahman" not in text
        assert "Kapoor" not in text
        assert "Physician:" not in text
        assert "Gender: Female" not in text

    # Ensure clinical facts are present
    assert any("118/76" in t for t in clause_texts)
    assert any("acne" in t.lower() for t in clause_texts)
    assert any("hirsutism" in t.lower() for t in clause_texts)
    assert any("pcos" in t.lower() or "polycystic" in t.lower() for t in clause_texts)


def test_segment_all_reports_provenance(parser, data_dir):
    """
    CRITICAL PHASE 2 CRITERION:
    Every single PDF in data/ produces clauses with valid page and section provenance.
    """
    pdf_files = list(data_dir.rglob("*.pdf"))
    total_clauses = 0

    for pdf_path in sorted(pdf_files):
        doc = parser.parse(pdf_path)
        clauses = ReportSegmenter.segment_document(doc)
        assert len(clauses) > 0, f"No clauses extracted from {pdf_path.name}"

        for c in clauses:
            assert c.page_number >= 1
            assert c.section_name is not None and len(c.section_name) > 0
            assert c.clause_id.startswith(pdf_path.stem)
            assert not HeaderNoiseFilter.is_noise(c.text)

        total_clauses += len(clauses)

    print(f"\n[OK] Successfully segmented {len(pdf_files)} reports into {total_clauses} clean clinical clauses!")
