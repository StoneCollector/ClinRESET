# ClinRESET Design Notes & Architectural Decisions

## 1. Problem Diagnosis of the Legacy System
The initial ClinRESET prototype provided valuable proof-of-concept components but suffered from several fundamental architectural limitations:
1. **Format Overfitting**: Hand-crafted, report-specific rules (`report_rules/*.py`) meant the system broke whenever formatting shifted slightly across different diagnostic centers.
2. **Metadata Fact Contamination**: Header details (e.g., patient name, age, doctor, hospital ID) were frequently swallowed into clause extraction, generating erroneous findings (e.g., classifying "61y / F" or doctor names as clinical concepts).
3. **Absence of a Fixed Benchmark**: Improvements made for one report type (e.g., echocardiograms) caused silent regressions on CT or ultrasound scans because there was no fixed gold set to evaluate against.
4. **Over-reliance on LLMs for Numerical Reasoning**: Allowing generative models to reason about numerical normalcy or reference ranges introduced hallucination risks that are unacceptable in healthcare NLP.

## 2. Core Architectural Principles

### A. Strict Division of Labor
| Responsibility | Engine | Rationale |
|---|---|---|
| Numbers, Ranges, Units | Deterministic Regex Grammar | High precision, zero hallucination, handles complex formats like `13 (6-11mm)` or `~15.8cm`. |
| Negation & Normalcy Cues | Rule-Based Negation Engine | High confidence on lexical triggers (`no evidence of`, `unremarkable`, `within normal limits`). |
| Concept Extraction | Small Language Model (SLM) + Grounding | Extracts nuanced anatomical/pathological terms while being strictly checked against source text. |
| Clinical Interpretation | Deterministic Clinical Table Engine | Compares extracted values directly against established clinical ranges. |
| Patient Explanation | Grounded LLM + Fact Consistency Check | Simplifies medical jargon into plain language, strictly forbidding numbers not present in source facts. |

### B. The Grounding Invariant
When the small model (e.g., Qwen2.5-1.5B 4-bit) outputs a candidate concept string:
1. The candidate string must have exact or high-substring token overlap with the input clause.
2. If the model hallucinates a term not present in the sentence, the grounding filter rejects it.

### C. Deterministic Normalcy & Range Invariant
Under no circumstances does an LLM judge whether a lab measurement or cardiac index is "normal" or "high". The system looks up the parsed value against clinical guideline tables. If a report provides an in-situ normal range (e.g., `(20-37mm)`), that explicit range takes precedence, parsed entirely by regex.

## 3. Salvaged Components Strategy
The following components are preserved in `legacy/` as reference:
- `legacy/extraction/`: PyMuPDF text & block extraction logic, OCR fallback patterns.
- `legacy/clinical_extraction/negation.py`: Regex-based trigger lists and scope bounds.
- `legacy/clinical_extraction/measurements.py`: Numerical measurement patterns and unit normalizations.
- `legacy/clinical_extraction/terminology/`: Lexicon mappings and abbreviation dictionaries.
- `legacy/significance/`: Range engines and alert classification logic.
- `legacy/clinical_explanation/`: Prompt templates and explanations structure.
- `legacy/web/`: FastAPI endpoints and UI assets.

All code introduced in `src/` will be cleanly designed, modular, and thoroughly tested against the gold set.
