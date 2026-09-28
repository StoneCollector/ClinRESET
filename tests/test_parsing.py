import os
from pathlib import Path
import pytest
from src.parsing.parser import PDFParser
from src.parsing.section_detector import SectionDetector
from src.parsing.models import ParsedDocument


@pytest.fixture
def parser():
    return PDFParser()


@pytest.fixture
def data_dir():
    cur_dir = Path(__file__).resolve().parent
    return cur_dir.parent / "data"


def test_parse_single_echo(parser, data_dir):
    echo_path = data_dir / "echo" / "PA01.pdf"
    assert echo_path.exists()

    doc = parser.parse(echo_path)
    assert isinstance(doc, ParsedDocument)
    assert doc.page_count == 2
    assert len(doc.full_text) > 500
    assert len(doc.sections) >= 3

    section_names = [s.name for s in doc.sections]
    assert "M-MODE PARAMETERS" in section_names
    assert "IMPRESSION" in section_names

    # Check metadata extraction
    assert doc.metadata["patient_id"] == "PA01" or doc.metadata["patient_name"] == "PA01"


def test_parse_general_report(parser, data_dir):
    gen_path = data_dir / "general" / "sample Medical Report4.pdf"
    assert gen_path.exists()

    doc = parser.parse(gen_path)
    assert doc.page_count == 1
    assert "Aisha Rahman" in doc.full_text

    section_names = [s.name for s in doc.sections]
    assert any("CHIEF COMPLAINT" in s for s in section_names)
    assert any("CLINICAL OBSERVATION" in s for s in section_names)


def test_parse_all_pdfs_in_data_no_crashes(parser, data_dir):
    """
    CRITICAL PHASE 1 CRITERION:
    Every single PDF in data/ parses, none crash.
    """
    pdf_files = list(data_dir.rglob("*.pdf"))
    assert len(pdf_files) >= 28, f"Expected at least 28 PDFs, found {len(pdf_files)}"

    successful_parses = 0
    errors = []

    for pdf_path in sorted(pdf_files):
        try:
            doc = parser.parse(pdf_path)
            assert doc.page_count > 0
            assert len(doc.full_text.strip()) > 0
            assert len(doc.sections) > 0
            successful_parses += 1
        except Exception as e:
            errors.append((str(pdf_path), str(e)))

    assert len(errors) == 0, f"Failed on {len(errors)} PDFs: {errors}"
    assert successful_parses == len(pdf_files)
    print(f"\n[OK] Successfully parsed {successful_parses} / {len(pdf_files)} PDFs without errors!")
