# ClinRESET Project Progress Tracker

## Status Summary
- **Current Phase**: Phase 0 (Setup + Gold Set)
- **Scaffold Status**: Completed (project structure, reference, notebooks, and legacy salvaging initialized)
- **Active Task**: Gold set definition and evaluation harness implementation

---

## Phase Checklist

- [ ] **Phase 0: Setup + Gold Set**
  - [x] Project scaffolding in `scratch/`
  - [x] Salvaged modules copied to `legacy/` (read-only)
  - [x] Reference data, sample reports, and notebooks copied
  - [x] Standing context (`AGENTS.md`) and project docs initialized
  - [ ] Curate and hand-label gold set facts across report modalities (~5 reports per modality)
  - [ ] Implement evaluation script (`evaluate_extractor.py`) reporting Precision, Recall, F1 for concepts, assertions, values, and units
  - [ ] Benchmark baseline / score table verification

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
- **2026-09-28**: Scaffolded `scratch/` directory. All subfolders created (`docs`, `data`, `reference`, `notebooks`, `legacy`, `src`, `.agents`). Copied 31 PDF reports across 6 modalities (`echo`, `general`, `ct scans`, `mri`, `ultrasound`, `xray`), reference files (`ClinRESET_medical_abbreviation_terminology_corpus.txt`, `sample_report.pdf`, `sample_report_expected.json`), `clause_extraction_model_test.ipynb`, and salvaged legacy modules.
