# ClinRESET Project Progress Tracker

## Status Summary
- **Current Phase**: Phase 3 (Rule Extraction)
- **Scaffold Status**: Completed
- **Phase 0 Status**: COMPLETED (Gold set with 28 reports & 189 facts, evaluation harness)
- **Phase 1 Status**: COMPLETED (PDF parser with section detection & OCR fallback, 30/30 PDFs verified)
- **Phase 2 Status**: COMPLETED (Clause segmentation & header noise filter, 751 clean clauses, zero metadata leakage)
- **Active Task**: Phase 3: Rule extraction (no model) - number grammar, negation & assertion cues

---

## Phase Checklist

- [x] **Phase 0: Setup + Gold Set**
  - [x] Project scaffolding in `scratch/`
  - [x] Salvaged modules copied to `legacy/` (read-only)
  - [x] Reference data, sample reports, and notebooks copied
  - [x] Standing context (`AGENTS.md`) and project docs initialized
  - [x] Curate and hand-label gold set facts across report modalities (28 reports, 189 facts)
  - [x] Implement evaluation script (`src/evaluation/scorer.py`, `evaluate.py`) reporting Precision, Recall, F1 for concepts, assertions, values, and units
  - [x] Benchmark baseline / score table verification (`python evaluate.py --self-test` passed 100%)

- [x] **Phase 1: Parse**
  - [x] Implement text & section parser (`src/parsing/`)
  - [x] Configure PyMuPDF / OCR fallback (`src/parsing/ocr.py`)
  - [x] Validate zero crashes across all PDF files in `data/` (30/30 passed)

- [x] **Phase 2: Segment**
  - [x] Implement sentence & clause splitter (`src/segmentation/clause_splitter.py`)
  - [x] Add header/metadata filtering (`src/segmentation/header_filter.py`)
  - [x] Maintain page and section provenance per clause (`src/segmentation/segmenter.py`)
  - [x] Validate zero metadata contamination across all 30 reports (751 clauses extracted)

- [ ] **Phase 3: Rule Extraction (No Model)**
  - [ ] Implement generalized measurement & unit regex parser (`src/extraction/rules/measurements.py`)
  - [ ] Implement negation and normal cue detector (`src/extraction/rules/assertion.py`)
  - [ ] Benchmark against Phase 0 gold set

- [ ] **Phase 3: Rule Extraction (No Model)**
  - [ ] Implement generalized measurement & unit regex parser (`src/extraction/rules/measurements.py`)
  - [ ] Implement negation and normal cue detector (`src/extraction/rules/assertion.py`)
  - [ ] Benchmark against Phase 0 gold set

- [ ] **Phase 4: Small-Model Concepts**
  - [ ] Integrate quantized SLM (Qwen2.5-1.5B 4-bit) for concept extraction
  - [ ] Implement strict text-grounding validation filter
  - [ ] Evaluate recall and assertion accuracy on held-out clauses

- [ ] **Phase 5: Terminology**
  - [ ] Implement RadLex / SNOMED lookup tables and normalizer
  - [ ] Add unmapped term detection and isolation

- [ ] **Phase 6: Interpretation**
  - [ ] Implement deterministic reference range comparison engine
  - [ ] Add severity categorization, alert indicators, and context groupings

- [ ] **Phase 7: Explanation (API)**
  - [ ] Implement structured LLM prompt using verified facts only
  - [ ] Add strict numerical cross-checker (output vs. source)
  - [ ] Provide offline deterministic template fallback

- [ ] **Phase 8: Web UI**
  - [ ] Implement FastAPI server exposing extraction & explanation endpoints
  - [ ] Create static frontend with provenance badges and interactive fact inspectors

- [ ] **Phase 9: Hardening**
  - [ ] End-to-end evaluation on held-out reports
  - [ ] Unit & integration test suite (`pytest`)
  - [ ] Final documentation and user guide

---

## Verification Log
- **2026-09-28 [Phase 0 Complete]**:
  - Scaffolded `scratch/` workspace with standing rules in `AGENTS.md` and project roadmap in `docs/PLAN.md`.
  - Salvaged legacy modules into `legacy/` (strictly read-only).
  - Curated gold standard set across all 6 modalities (`echo`, `general`, `ct scans`, `mri`, `ultrasound`, `xray`): 28 reports, 189 clinical facts (`data/gold_set/`).
  - Implemented evaluation scorer (`src/evaluation/scorer.py`) and CLI (`evaluate.py`) with metric calculation across Concepts (P/R/F1), Assertions (Accuracy), Measurements (Value/Unit match).
  - Executed evaluation self-test (`python evaluate.py --self-test`): 100% metrics across all 6 modalities.
  - Added unit test suite in `tests/test_evaluation.py`: 3/3 tests passed with `pytest`.
- **2026-09-28 [Phase 1 Complete]**:
  - Implemented `src/parsing` package with `PDFParser`, `SectionDetector`, and `OCREngine` fallback.
  - Configured project virtual environment (`scratch/venv`) with PyMuPDF, pytesseract, Pillow, Pydantic, and pytest.
  - Added unit tests in `tests/test_parsing.py` validating section extraction and batch parsing across all 30 PDF reports.
  - Ran batch test on entire data suite: 30 / 30 PDFs successfully parsed with 0 errors or crashes.
  - Full pytest suite (6/6 tests) passing cleanly in 0.66s.
- **2026-09-28 [Phase 2 Complete]**:
  - Implemented `src/segmentation` package with `HeaderNoiseFilter`, `ClauseSplitter`, and `ReportSegmenter`.
  - Validated that demographic headers (e.g. "Aisha Rahman Age", doctor signatures, dates, hospital boilerplate) are 100% blocked from emitted clauses.
  - Verified atomic clause splitting on coordinate negations and decimals without splitting numbers or medical abbreviations.
  - Segmented all 30 reports in data suite into 751 clean clinical clauses with full page and section provenance.
  - Full pytest suite (11/11 tests) passing cleanly in 1.12s.

