# ClinRESET Re-Architecture & Development Log: Conversation 1
**Project Workspace:** `c:\Projects\NLP\scratch/`  
**Parent Workspace (Strictly Read-Only):** `c:\Projects\NLP`  
**Virtual Environment:** `c:\Projects\NLP\scratch\venv` (Python 3.10.0)  
**Latest Git Commit:** `60330bb`  
**Test Suite Status:** 52/52 Unit & Integration Tests Passing (100% green)

---

## 1. Executive Summary & Core Mission

ClinRESET is an end-to-end clinical document simplification platform that transforms complex medical imaging reports (Echocardiograms, CT Scans, MRIs, Ultrasounds, X-Rays, and General Medical Reports) into clear, empathetic, 6th-grade reading level explanations for patients.

### Why the Project Was Rebuilt From Scratch
The previous implementation suffered from critical safety and architecture defects:
1. **Demographic Metadata Contamination:** Patient names, ages, dates, and doctor signatures were leaking directly into clinical clauses and LLM prompts.
2. **Ungrounded LLM Hallucinations:** Free-form generative LLMs were inventing non-existent clinical conditions, misjudging normal anatomy as abnormal, and hallucinating medical measurements.
3. **Fabricated Reference Ranges:** Models were inventing standard lab ranges rather than reading reported in-situ reference ranges directly from the document text.

### The Standing Architectural Invariants (`AGENTS.md`)
To guarantee clinical safety and strict scientific reproducibility:
1. **Numbers are Immutable:** Numbers, decimal values, and units come strictly from deterministic regex grammars. No LLM ever emits or modifies a numerical measurement.
2. **Report Ranges Rule:** The system strictly compares values against reference intervals explicitly printed in the report. If no range is reported, it flags `NO_REFERENCE_RANGE_SUPPLIED` and categorizes the finding as contextual (`GREY`), never inventing arbitrary population thresholds.
3. **Text-Grounding Validation:** Every concept extracted by any model must pass an exact character-level substring grounding check (`GroundingValidator`) against the source sentence.
4. **Offline-First with Dynamic Cache Enrichment:** All critical path operations run 100% locally and offline. External APIs (SNOMED CT via EMBL-EBI OLS4) are selectively queried for new atomic concepts, cached locally, and learned forever.
5. **Parent Directory is Read-Only:** All new work lives exclusively in `scratch/`.

---

## 2. Chronological Development & Conversation History

### Phase 0: Setup, Scaffolding & Gold Set Curation (Commit: `4ae4bb6`)
- **Action:** Scaffolded clean directory tree inside `scratch/`. Migrated reference documents, sample reports, and notebooks. Preserved salvaged legacy modules inside `legacy/` as read-only references.
- **Gold Standard Dataset:** Hand-labeled 28 clinical reports comprising 189 ground-truth facts across all 6 modalities (`echo`, `general`, `ct scans`, `mri`, `ultrasound`, `xray`) located in `data/gold_set/`.
- **Evaluation Harness:** Built `src/evaluation/scorer.py` and `evaluate.py` to compute Precision, Recall, and F1 across Concepts, Assertions, Values, and Units.
- **Validation:** Executed self-test verification (`python evaluate.py --self-test`) achieving 100% baseline accuracy across all modalities.

### Phase 1: PDF Parsing & OCR Fallback (Commit: `b0ce9dc`)
- **Action:** Implemented `src/parsing/` (`PDFParser`, `SectionDetector`, `OCREngine`).
- **Features:** High-speed digital text extraction via PyMuPDF with automatic fallback to OCR (pytesseract) when character density is below threshold. Structured document models with `ParsedDocument`, `ParsedPage`, and `Section`.
- **Validation:** Batch parsed all 30 PDF reports in the dataset with 0 errors or crashes (`tests/test_parsing.py`).

### Phase 2: Segmentation & Metadata Filtering (Commit: `8c16ce2`)
- **Action:** Implemented `src/segmentation/` (`HeaderNoiseFilter`, `ClauseSplitter`, `ReportSegmenter`).
- **Features:**
  - `HeaderNoiseFilter`: Regex rules blocking patient demographic lines ("Aisha Rahman Age: 61y", dates, doctor headers, hospital boilerplate).
  - `ClauseSplitter`: Regex splitting on coordinate semicolons, bullet points, and contrastive conjunctions ("...but no focal lesion") without breaking decimal points (`15.8cm`) or medical abbreviations (`L.V.`).
  - Table-row clause processing for structured parameter tables (M-Mode, Doppler).
- **Validation:** Extracted 751 clean clinical clauses from the 30 PDFs with **0% demographic metadata leakage** (`tests/test_segmentation.py`).

### Phase 3: Rule Extraction - No Model (Commit: `ef648cd`)
- **Action:** Implemented `src/extraction/rules/` (`MeasurementParser`, `AssertionClassifier`, `RuleExtractor`).
- **Features:**
  - Deterministic regex grammars for inline measurements (`118/76 mmHg`, `PASP=34mmHg`, `15.8cm`).
  - In-situ reference range parser extracting inclusive brackets (`13 (06-11mm)` -> value 13.0, range [6.0, 11.0] mm).
  - Deterministic assertion detector classifying `PRESENT`, `ABSENT` ("no evidence of", "ruled out"), and `NORMAL` ("within normal limits", "unremarkable").
- **Benchmark:** Evaluated against Phase 0 Gold Set (`python evaluate.py --rules`): achieved **86.4% overall assertion accuracy** (100% on CT, General, Ultrasound, and X-ray).

### Phase 4: Grounded Concept Extraction & Model Plugins (Commits: `05c5413`, `c8d90ec`)
- **Action:** Implemented `src/extraction/model/` (`GroundingValidator`, `ConceptExtractor`, `model_plugins.py`).
- **User Request:** *“create another py file named 'model_plugins.py' which will have a methodology selector which will allow me to switch between any of these options. I would like to try them all and keep it as an option to switch between them”*
- **Solution:** Built `ModelSelector` exposing 4 distinct extraction backends:
  1. `heuristic`: Pure deterministic clinical NLP. 0 dependencies, instant (<1ms), 0 memory, zero hallucination.
  2. `ollama`: Local 4-bit quantized SLMs (e.g. Qwen2.5:1.5b via REST API `http://localhost:11434`).
  3. `hf_api`: Hugging Face Serverless Inference API via token (`HUGGINGFACE_API_KEY`).
  4. `transformers`: Local PyTorch / Transformers model weights pipeline.
- **Top-Level CLI:** Created `scratch/model_plugins.py` with `--list`, `--backend <name>`, and `--compare` flags.
- **Benchmark:** Evaluated on benchmark clauses from `clause_extraction_model_test.ipynb`: achieved **100% concept recall (21/21)** and **0 ungrounded hallucinations**.

### Phase 5: Terminology Normalization & SNOMED CT API (Commit: `655c844`)
- **User Exploration:** User inquired about SNOMED APIs without mandatory account verification and asked whether downloaded terminology could be cached for offline use.
- **API Investigation:** Identified that official SNOMED International browser endpoints block programmatic access with HTTP 405. Selected **EMBL-EBI OLS4 API** (`https://www.ebi.ac.uk/ols4/api/search?q={query}&ontology=snomed`) which is 100% free, requires zero credentials, and returns canonical SNOMED Concept IDs and synonyms.
- **Architecture:** Implemented `src/terminology/` with the **Offline-First with Dynamic Cache Enrichment** pattern:
  - Local 554-abbreviation corpus (`reference/ClinRESET_medical_abbreviation_terminology_corpus.txt`).
  - Persistent disk cache `data/terminology_cache.json`.
  - Non-medical noise and unmapped terms safely isolated with `is_known=False`.

### Phase 6: Deterministic Clinical Interpretation (Commit: `8b30cd7`)
- **Action:** Implemented `src/interpretation/` (`range_engine.py`, `classifier.py`, `clusters.py`, `engine.py`).
- **Features:**
  - Range comparator parsing inclusive thresholds (`06-11mm`, `55-74%`, `12-16 g/dL`).
  - Triage Alert Level categorization:
    - 🟢 `GREEN`: Normal / reassuring / within reported range / absent negative finding.
    - 🟡 `YELLOW`: Notable qualitative finding present (e.g. disc bulge, hepatomegaly).
    - 🟠 `ORANGE`: Outside reported reference range.
    - 🔴 `RED`: Urgent life-threatening triggers (e.g. large pneumothorax, pericardial tamponade).
    - ⚪ `GREY`: Contextual measurements without explicit reference ranges (e.g. PASP=34).
  - Contextual Finding Clusters: Groups related parallel findings (Cardiovascular, Respiratory, Hepatobiliary, Spinal) without asserting medical causation.

### Phase 7: Fact-Grounded Patient Explanation (Commit: `a1e7ec7`)
- **Action:** Implemented `src/explanation/` (`verifier.py`, `templates.py`, `llm_explainer.py`, `engine.py`).
- **Features:**
  - `NumericalCrossChecker`: Strict invariant guard checking every number in generated text against source report facts. Any unauthorized or deviating number is rejected immediately.
  - Deterministic 6th-grade reading level template generator producing plain-language summaries, organized finding cards, layman translations, and empowered questions for the patient's doctor.

### Phase 8: Web UI & Methodology Studio (Commits: `67bb091`, `3b961b0`, `60330bb`)
- **User Request:** *“the model_plugins.py setting code? make it a UI page too such that the user himself can select the method (just for testing and making it easy for us) and even setup the credentials there like endpoint, api key etc”*
- **Solution:** Built a full FastAPI web server and single-page modern frontend with two primary views:
  1. **Clinical Report Simplifier (`#simplifier`)**: Drag-and-drop PDF uploader, 1-click sample selector, triage counter bar, finding clusters, findings table, and interactive Fact Provenance Inspector modal.
  2. **Methodology Studio (`#studio`)**: Engine status cards (`heuristic`, `ollama`, `hf_api`, `transformers`), credential configuration form, and live extraction testing playground.
- **Launcher:** Created `scratch/run_web.py` (`python run_web.py --port 8000 --reload`).

---

## 3. Real-World Issues Encountered & Resolved in Phase 8

### Issue 1: `TypeError: Cannot read properties of undefined (reading 'map')`
- **Symptom:** Upon clicking "Simplify Report" in the browser, an alert popped up with this error.
- **Root Cause:** In `app.js`, `renderClusters` expected `cluster.findings.map(...)`, but the backend model `FindingCluster` defined the property as `matched_concepts`.
- **Resolution:**
  - Updated `app.js` to safely resolve `cluster.matched_concepts || cluster.findings || []`.
  - Updated `src/web/pipeline.py` to emit both `matched_concepts` and `findings` for backwards compatibility.

### Issue 2: Console Error: `404 Not Found (/favicon.ico)`
- **Symptom:** Browser logged a red 404 for `/favicon.ico`.
- **Resolution:** Added an explicit `@app.get("/favicon.ico")` handler in `src/web/app.py` returning `HTTP 204 No Content`.

### Issue 3: "Stuck on Loading" (35s Delay -> 500x Speedup)
- **Symptom:** User selected `echo/PA01.pdf` and reported that the UI was "stuck on loading".
- **Investigation:**
  - Profiling revealed that `TerminologyNormalizer(online=True)` was attempting to look up 17 multi-word clauses (e.g. *"ON INTERROGATING WITH PULSE & CONTINUOUS WAVE DOPPLER IT WAS FOUND THAT THERE IS"*) sequentially against the public EMBL-EBI OLS4 API.
  - Each unmapped clause took 1.5s–3.5s across multiple fallback endpoints, totaling **35.03 seconds** of blocking network I/O.
- **Resolution ([Commit `60330bb`](file:///c:/Projects/NLP/scratch)):**
  1. **Offline-First Default:** Set web pipeline to use local cached terminology by default, dropping execution time from **34.2s to 0.064s (64 milliseconds)**.
  2. **Candidate Filter Guard:** Configured `TerminologyNormalizer` to only query online APIs for plausible atomic concept names ($\le 4$ words, $\le 35$ characters, no sentence delimiters or punctuation).
  3. **Negative Caching:** Unmapped concepts are immediately recorded in `self.cache` with `is_known=False` so they never touch the network a second time.
  4. **Fast Timeout:** Reduced network socket timeout to 0.8s.

---

## 4. Architecture & Workspace Structure

```
c:\Projects\NLP\scratch/
├── conversation_1.md                 # Complete historical log of conversation & decisions
├── run_web.py                        # Standalone FastAPI/Uvicorn server launcher
├── model_plugins.py                  # Standalone CLI for testing extraction methodologies
├── evaluate.py                       # Evaluation CLI & gold-set benchmark harness
├── pytest.ini                        # Pytest configuration
├── data/
│   ├── ct scans/                     # Sample CT scan PDFs
│   ├── echo/                         # Sample Echocardiogram PDFs
│   ├── general/                      # Sample General Medical Report PDFs
│   ├── mri/                          # Sample MRI PDFs
│   ├── ultrasound/                   # Sample Ultrasound PDFs
│   ├── xray/                         # Sample X-Ray PDFs
│   ├── gold_set/                     # 28 hand-labeled gold reports (189 clinical facts)
│   └── terminology_cache.json        # Persistent local terminology cache (SNOMED IDs, layman terms)
├── docs/
│   ├── PLAN.md                       # Comprehensive 10-phase project plan
│   └── PROGRESS.md                   # Real-time task tracker and verification log
├── src/
│   ├── parsing/                      # Phase 1: PDF text parser, OCR fallback, section detector
│   ├── segmentation/                 # Phase 2: Header filter, clause splitter, document segmenter
│   ├── extraction/
│   │   ├── rules/                    # Phase 3: Deterministic regex measurements & assertions
│   │   ├── model/                    # Phase 4: Grounded concept extractor & model plugins
│   │   └── hybrid_extractor.py       # Phase 4: Hybrid rule + model fact extractor
│   ├── terminology/                  # Phase 5: Local abbreviation corpus & EMBL-EBI SNOMED client
│   ├── interpretation/               # Phase 6: Reference range comparator, triage alerts, clusters
│   ├── explanation/                  # Phase 7: Numerical cross-checker & patient explainer
│   └── web/                          # Phase 8: FastAPI backend & Single-Page Web Application
│       ├── app.py                    # FastAPI application definition
│       ├── pipeline.py               # Unified 7-phase end-to-end report simplification pipeline
│       ├── state.py                  # Runtime configuration singleton (credentials & backends)
│       ├── routes/
│       │   ├── reports.py            # Upload PDF, run sample report, list sample files
│       │   └── methodologies.py      # Configure credentials, switch engine, test live sentence
│       └── static/
│           ├── index.html            # Single-page UI (Simplifier + Studio + Inspector modal)
│           ├── css/style.css         # Modern clinical dark-mode theme
│           └── js/app.js             # Client-side controller (tabs, uploads, inspector modal)
└── tests/
    ├── test_evaluation.py            # Gold set & scorer unit tests (3 tests)
    ├── test_parsing.py               # PDF parser & OCR unit tests (3 tests)
    ├── test_segmentation.py          # Header filter & clause splitting tests (5 tests)
    ├── test_rule_extraction.py       # Deterministic rule & assertion tests (5 tests)
    ├── test_model_concepts.py        # Grounding & benchmark recall tests (2 tests)
    ├── test_model_plugins.py         # Multi-backend plugin tests (7 tests)
    ├── test_terminology.py           # Abbreviation, cache, & OLS API tests (7 tests)
    ├── test_interpretation.py        # Range parsing, triage alerts, cluster tests (6 tests)
    ├── test_explanation.py           # Numerical cross-checker & template tests (5 tests)
    └── test_web.py                   # Web API, Studio, & end-to-end pipeline tests (9 tests)
```

---

## 5. Critical Invariants for the Next Developer

If you are continuing work on this codebase, adhere strictly to these rules:

1. **Do Not Touch Parent Directory:** `c:\Projects\NLP` is the original codebase and is strictly read-only. Work only inside `c:\Projects\NLP\scratch/`.
2. **Always Use the Virtual Environment:** Execute Python, Pip, Pytest, and Uvicorn using:
   `c:\Projects\NLP\scratch\venv\Scripts\python.exe` or `.\venv\Scripts\pytest.exe`.
3. **No Hallucinated Numbers:** Never allow an LLM or prompt to generate numerical values independently. All values must trace directly to regex measurement grammars or explicit report text.
4. **Number Extraction Boundaries:** When writing regular expressions for numbers, do not rely on `\b\d+\b` because unit characters (e.g. `11mm`, `15.8cm`) adhere directly to digits. Use `re.compile(r"\d+(?:\.\d+)?")`.
5. **Organ System Precedence:** In keyword classification, organ-specific terms (e.g., "renal", "kidney") must take precedence over generic morphological terms (e.g., "calculus", "calculi") to prevent renal calculi from misclassifying under the GI system.
6. **Git Commits:** Make exactly one atomic git commit per phase and maintain `docs/PROGRESS.md`.

---

## 6. How to Run & Test the Application

### Running the Web Server
From `c:\Projects\NLP\scratch`:
```powershell
.\venv\Scripts\python.exe run_web.py --port 8000 --reload
```
- **Web App Interface:** http://127.0.0.1:8000
- **Methodology Studio:** http://127.0.0.1:8000#studio
- **Interactive Swagger API Docs:** http://127.0.0.1:8000/docs

### Running the Test Suite
```powershell
.\venv\Scripts\pytest.exe -v
```
*(Currently 52/52 tests passing in under 12 seconds).*

### Testing Methodologies via CLI
```powershell
# List available engines
.\venv\Scripts\python.exe model_plugins.py --list

# Test a single sentence using heuristic NLP
.\venv\Scripts\python.exe model_plugins.py --backend heuristic --sentence "Liver is enlarged (~15.8cm), no focal lesion seen."

# Compare all available backends side-by-side
.\venv\Scripts\python.exe model_plugins.py --compare --sentence "Grade 1 left ventricular diastolic dysfunction."
```

---

## 7. Immediate Next Steps: Phase 9 (Hardening & End-to-End Evaluation)

The project is currently at **Phase 9** (the final roadmap phase). The next developer should proceed with:
1. **End-to-End Gold Set Evaluation:** Run the full pipeline (Parse -> Segment -> Hybrid Extract -> Normalize -> Interpret -> Explain) across all 28 gold-standard reports in `data/gold_set/` using `evaluate.py`.
2. **Benchmark Table Generation:** Generate final metric tables (Concept Precision/Recall/F1, Assertion Accuracy, Measurement Match, Numerical Grounding Discrepancy Rate).
3. **Edge Case Hardening:** Test empty reports, single-line scans, corrupted PDFs, and non-English clinical abbreviations.
4. **Documentation & User Guide:** Finalize `README.md` and complete documentation for production handoff.
