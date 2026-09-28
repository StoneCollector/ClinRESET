# ClinRESET Master Implementation Plan

This roadmap governs the clean re-implementation of ClinRESET inside `scratch/`.

## Phase Table

| # | Phase | What Gets Built | Done When | Salvage from Legacy |
|---|---|---|---|---|
| **0** | **Setup + Gold Set** | Repo scaffold, folders, `data/` copied over. Hand-labeled ground truth facts (`concept`, `assertion`, `value`, `unit`) for ~5 reports per type. Scoring harness script. | Scoring script runs and prints benchmark metrics against gold set | `data/`, `reference/sample_report_expected.json` |
| **1** | **Parse** | Robust PDF-to-text pipeline extracting clean text and structured sections, with OCR fallback for scanned reports. | Every PDF in `data/` parses without errors or crashes | `legacy/extraction/` |
| **2** | **Segment** | Sentence and clause boundary detector. Header noise filter (excludes Name, Age, Sex, Date, Ref By so metadata is never treated as clinical facts). Maintains page/section provenance. | "Aisha Rahman Age" style metadata never appears in extracted facts | `legacy/extraction/normaliser.py`, clause splitters |
| **3** | **Rule Extraction (No Model)** | Generic measurement & number grammar (e.g., `13 (6-11mm)`, `~15.8cm`, multi-column tables). Negation and normal cue detectors for `ABSENT`, `NORMAL`, and `PRESENT` assertions. | Measurement parsing and assertion score evaluated on gold set | `legacy/clinical_extraction/negation.py`, `legacy/clinical_extraction/measurements.py` |
| **4** | **Small-Model Concepts** | Quantized lightweight SLM (Qwen2.5-1.5B 4-bit) extracting finding concepts per clause. String grounding filter discarding ungrounded hallucinatory terms. | $\ge 90\%$ recall and assertion precision on held-out clauses | `notebooks/clause_extraction_model_test.ipynb` |
| **5** | **Terminology** | Ontology normalization using RadLex / SNOMED lookup tables. Unknown or out-of-vocabulary concepts flagged clearly. | Concepts normalized or flagged with provenance; unknown terms isolated | `legacy/clinical_extraction/terminology/` |
| **6** | **Interpretation** | Deterministic reference range evaluation, severity classification, alert color-coding, and organ/system context groupings. | Exact reproduction of deterministic interpretation on reference outputs | `legacy/significance/` |
| **7** | **Explanation (API)** | Grounded single API call per report using verified facts. Strict number-matching verification comparing output against input facts. Template fallback when offline. | Zero discrepancy between explanation numbers and source numbers | `legacy/clinical_explanation/` |
| **8** | **UI** | Clean FastAPI API backend and responsive web frontend. Interactive report view with provenance badges for model vs. rule facts. | End-to-end user workflow: upload PDF -> view structured report | `legacy/web/` |
| **9** | **Hardening** | Held-out test evaluation, automated pytest test suite, error analysis, comprehensive README and architecture guide. | All tests pass, final evaluation report generated | Clean unit tests |

## Architectural Invariants
1. **Safety First**: Clinical interpretation and numerical ranges are strictly deterministic. The LLM is never allowed to invent or adjust ranges.
2. **Grounding Verification**: Any concept extracted by an ML model must pass a verbatim/token-overlap grounding check against the input clause.
3. **Decoupled Phases**: Phases 0–3 provide a functional baseline without requiring any GPU or deep learning weights.
4. **Clean Codebase**: All production code resides in `src/`. `legacy/` is purely read-only reference.
