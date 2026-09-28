# ClinRESET Project Progress Tracker

## Status Summary
- **Current Phase**: Phase 1 (Parse)
- **Scaffold Status**: Completed
- **Phase 0 Status**: COMPLETED (Gold set with 28 reports & 189 facts, evaluation harness with score table)
- **Active Task**: Phase 1: PDF to clean text and sections with OCR fallback

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


- [ ] **Phase 1: Parse**
  - [ ] Implement text & section parser (`src/parsing/`)
  - [ ] Configure PyMuPDF / OCR fallback (Tesseract)
  - [ ] Validate zero crashes across all PDF files in `data/`

- [ ] **Phase 2: Segment**
  - [ ] Implement sentence & clause splitter (`src/segmentation/`)
  - [ ] Add header/metadata filtering (filter out Name, Age, Sex, Date, Ref By)
  - [ ] Maintain page and section provenance per clause

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

