# ClinRESET: Clinical Report Standardization & Explanation

## Core Purpose
ClinRESET parses medical reports (PDF/images), extracts clinical facts (concepts, measurements, assertions) with grounded deterministic accuracy, and generates simple, patient-comprehensible explanations without hallucination.

## Non-Negotiables & Safety Invariants
1. **Model Never Judges Ranges**: LLMs/SLMs never judge normal vs abnormal and never invent reference ranges. Interpretation is 100% deterministic (rules/reference tables).
2. **Strict Grounding**: Every model-extracted concept must be verbatim or grounded in source text. Drop ungrounded findings.
3. **No Per-Report Hardcoding**: No report-type-specific hardcoded lexicons. Use generalized number grammar and standardized ontology (RadLex/SNOMED).
4. **Numbers from Regex Only**: Numerical values, intervals, and units come strictly from deterministic regex grammars, never from LLMs.
5. **Legacy is Read-Only**: `legacy/` is purely reference. Never import from or edit anything in `legacy/`. Clean implementations belong in `src/`.

## Phased Implementation Roadmap
Work on **one phase at a time**. Do not jump ahead or expand scope.
- **Phase 0: Setup + Gold Set** -> Hand-label ~5 reports per type; extractor scoring script printing evaluation table.
- **Phase 1: Parse** -> PDF to clean text/sections with OCR fallback. Zero crashes across all test PDFs.
- **Phase 2: Segment** -> Sentences/clauses splitting, header metadata filtering (patient info never becomes clinical facts).
- **Phase 3: Rule Extraction** -> Generic number grammar, negation cues, assertion classification (`PRESENT`, `ABSENT`, `NORMAL`).
- **Phase 4: Small-Model Concepts** -> Qwen2.5-1.5B (4-bit) extracts concepts per clause; text-grounding validation filter.
- **Phase 5: Terminology** -> RadLex / SNOMED lookup for canonical concepts; flag unknown concepts.
- **Phase 6: Interpretation** -> Range comparison, alert flags, context groupings (deterministic).
- **Phase 7: Explanation API** -> Grounded report-level patient explanation with offline template fallback; verified numbers only.
- **Phase 8: Web UI** -> FastAPI backend + clean frontend with model-derived badges and full traceability.
- **Phase 9: Hardening** -> Held-out evaluations, error analysis, automated test suite, documentation.

## Verification & Operating Discipline
- **Execution First**: Never claim a feature works unless you executed it. Show actual terminal/test output. If execution failed, disclose immediately.
- **Commit Cadence**: Maintain dedicated git commits per phase.
- **Session Continuity**: Update `docs/PROGRESS.md` at each phase boundary so new sessions can seamlessly resume.
