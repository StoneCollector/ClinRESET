# ClinRESET — Clinical Report Simplification Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/pytest-52%20passed-brightgreen.svg)](https://docs.pytest.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Deterministic%20%2B%20SLM-orange.svg)]()

ClinRESET is an end-to-end clinical document simplification platform that transforms complex medical imaging and laboratory reports into empathetic, clear, 6th-grade reading level explanations for patients.

It eliminates the three most common failures of generative medical AI:
1. **Zero Demographic Contamination:** 100% of patient names, ages, dates, and doctor signatures are filtered before reaching extraction or explanation layers.
2. **Zero Numerical Hallucination:** Measurements, units, and values are parsed through deterministic regex grammars and guarded by a strict `NumericalCrossChecker`.
3. **Factual Reference Bounds:** The system strictly evaluates against reported in-situ reference ranges; it never invents standard lab ranges or assumes normal values.

---

## Quickstart & Run Instructions

### 1. Prerequisites
- **Python**: Version 3.10 or higher.
- **Git**

### 2. Environment Setup

Clone the repository and switch to the `remake` branch:
```bash
git clone https://github.com/StoneCollector/ClinRESET.git
cd ClinRESET
git checkout remake
```

Create and activate a virtual environment:
```powershell
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

Install the dependencies:
```bash
pip install -r requirements.txt
# Or manually install core packages:
pip install fastapi uvicorn python-multipart pymupdf pydantic pytest httpx pillow pytesseract
```

---

## 3. Running the Web Application

To launch the full interactive web application with the **Clinical Report Simplifier** and **Methodology Studio**:

```powershell
python run_web.py --port 8000 --reload
```

Once running, navigate to:
- 🌐 **Web Interface:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- ⚙️ **Methodology Studio:** [http://127.0.0.1:8000#studio](http://127.0.0.1:8000#studio)
- 📚 **Interactive Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Features in the Web App
1. **Report Simplifier Tab:**
   - Drop any medical imaging PDF (Echo, CT, MRI, Ultrasound, X-Ray) or select a pre-loaded sample.
   - Click **"Simplify Report"** to view:
     - Plain-language patient summary.
     - Triage status counter bar (🟢 Green, 🟡 Yellow, 🟠 Orange, 🔴 Red, ⚪ Grey).
     - Clinical finding clusters (e.g., Cardiovascular, Respiratory).
     - Detailed findings table.
   - Click any finding in the table to open the **Fact Provenance Inspector**, displaying the exact verbatim clause, source page, section, and SNOMED CT code.
2. **Methodology Studio Tab:**
   - View real-time status of all 4 extraction engines (`heuristic`, `ollama`, `hf_api`, `transformers`).
   - Switch the active backend dynamically.
   - Configure local endpoints (Ollama base URL) or cloud API keys (Hugging Face token).
   - Test extraction on live clinical sentences in real time with millisecond latency metrics.

---

## 4. Running the Test Suite

To run all 52 unit and integration tests across all pipeline phases:

```powershell
pytest -v
```

All 52 tests execute cleanly in under 12 seconds:
- `test_parsing.py`: PDF digital parsing & OCR fallback.
- `test_segmentation.py`: Noise filtering & clause splitting.
- `test_rule_extraction.py`: Measurements, units, & assertions.
- `test_model_concepts.py`: Grounding validator & benchmark recall.
- `test_model_plugins.py`: Engine selector & multi-backend execution.
- `test_terminology.py`: Abbreviation corpus, SNOMED API, & persistent caching.
- `test_interpretation.py`: Range comparisons, alert levels, & clusters.
- `test_explanation.py`: Numerical cross-checking & patient summaries.
- `test_web.py`: FastAPI routes, live sandbox, & sample processing.

---

## 5. CLI Tools & Standalone Execution

### Testing Extraction Methodologies via CLI
```powershell
# List available backends and their dependencies
python model_plugins.py --list

# Test a sentence with the pure deterministic engine (< 1 ms, 0 dependencies)
python model_plugins.py --backend heuristic --sentence "Liver is enlarged (~15.8cm), no focal lesion seen."

# Compare all installed engines side-by-side
python model_plugins.py --compare --sentence "Grade 1 left ventricular diastolic dysfunction, no pericardial effusion."
```

### Running Benchmark Evaluation against Gold Standard Set
```powershell
# Verify gold set facts & run evaluation self-test (100% baseline verification)
python evaluate.py --self-test

# Benchmark Phase 3 deterministic rule extractor against gold reports
python evaluate.py --rules
```

---

## 6. Architecture & System Workflow

```
[Clinical PDF Report]
       │
       ▼
1. PDF Parser (PyMuPDF + OCR Fallback)
       │
       ▼
2. Segmenter (Header Noise Filter + Atomic Clause Splitter)
       │
       ▼
3. Hybrid Fact Extractor
   ├── Regex Measurement Grammar (Values, Units, Reference Ranges)
   └── Grounded Concept Extractor (Heuristic / Ollama / HF API / Transformers)
       │
       ▼
4. Terminology Normalization (Offline-First Abbreviation Corpus + OLS4 SNOMED API)
       │
       ▼
5. Clinical Interpretation (Range Comparator + Triage Alerts + Finding Clusters)
       │
       ▼
6. Patient Explanation (Deterministic Templates + Numerical Cross-Checker Guard)
       │
       ▼
[Interactive Web UI & Fact Provenance Inspector]
```

---

## 7. Project Documentation

- **[conversation_1.md](conversation_1.md)**: Complete chronological transcript of all architecture discussions, decisions, benchmark logs, and debugging records.
- **[docs/PROGRESS.md](docs/PROGRESS.md)**: Real-time 10-phase roadmap and verification log.
- **[docs/PLAN.md](docs/PLAN.md)**: Comprehensive architectural roadmap and system design.
- **[AGENTS.md](AGENTS.md)**: Standing invariants and safety rules.
