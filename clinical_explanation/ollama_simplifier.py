"""
clinical_explanation/ollama_simplifier.py

Plain-language simplification layer powered by a local Ollama model.

Takes a technical medical definition (from BioPortal / Disease Ontology)
combined with the patient's specific result (value, unit, reference range,
status) and returns a 2-3 sentence patient-friendly explanation.

Caching
-------
Every successfully simplified explanation is stored in a local JSON cache
(ollama_cache.json) next to this file. The same term + status combination is
never re-processed — subsequent reports get the cached result instantly.

Privacy
-------
Only the concept name and its technical definition are sent to the local
Ollama server. The patient's name, DOB, and other PII from the original PDF
are never included in the prompt.

Usage
-----
    from clinical_explanation.ollama_simplifier import simplify_explanation

    plain = simplify_explanation(
        concept_name="Hemoglobin",
        technical_definition="The major protein of erythrocytes...",
        value=14.5,
        unit="g/dL",
        reference_range="13.5 - 17.5",
        status="NORMAL",   # "NORMAL", "HIGH", "LOW", or "UNKNOWN"
    )
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("clinical_explanation.ollama_simplifier")

# ---------------------------------------------------------------------------
# Configuration — read from config.py so everything is in one place
# ---------------------------------------------------------------------------
try:
    from clinical_explanation.config import (
        OLLAMA_BASE_URL,
        OLLAMA_ENABLED,
        OLLAMA_MODEL,
        OLLAMA_TIMEOUT,
    )
except ImportError:
    # Fallback defaults if config.py doesn't have Ollama settings yet
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "mistral:latest"
    OLLAMA_TIMEOUT = 120.0
    OLLAMA_ENABLED = True

# ---------------------------------------------------------------------------
# Persistent cache
# ---------------------------------------------------------------------------

_CACHE_FILE = Path(__file__).resolve().parent / "ollama_cache.json"
_cache_lock = threading.Lock()


def _load_cache() -> dict[str, str]:
    """Load the on-disk cache into memory."""
    if _CACHE_FILE.exists():
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    """Persist the cache to disk (thread-safe)."""
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.warning("Could not save Ollama cache: %s", e)


# In-memory cache (loaded once, flushed on every write)
_memory_cache: dict[str, str] = _load_cache()


def _cache_key(concept_name: str, status: str) -> str:
    """Stable cache key for a concept + status combination."""
    return f"{concept_name.lower().strip()}::{status.upper()}"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_STATUS_CONTEXT = {
    "HIGH": (
        "The patient's result is ABOVE the normal reference range. "
        "Mention this clearly but calmly, and suggest they discuss it with their doctor."
    ),
    "LOW": (
        "The patient's result is BELOW the normal reference range. "
        "Mention this clearly but calmly, and suggest they discuss it with their doctor."
    ),
    "NORMAL": (
        "The patient's result is within the normal reference range. "
        "Reassure them that this is a good result."
    ),
    "UNKNOWN": (
        "No reference range was available to compare against. "
        "Simply explain what the test measures without assigning a status."
    ),
}


def _build_prompt(
    concept_name: str,
    technical_definition: str,
    value: Optional[Any],
    unit: Optional[str],
    reference_range: Optional[str],
    status: str,
) -> str:
    """Build the prompt sent to the Ollama model."""

    val_str = ""
    if value is not None:
        val_str = f"\nPatient's result: {value}{(' ' + unit) if unit else ''}"

    ref_str = ""
    if reference_range:
        ref_str = f"\nNormal range: {reference_range}{(' ' + unit) if unit else ''}"

    status_instruction = _STATUS_CONTEXT.get(status.upper(), _STATUS_CONTEXT["UNKNOWN"])

    prompt = f"""You are a friendly medical report assistant helping a patient understand their lab result.

Test name: {concept_name}
Technical definition: {technical_definition}{val_str}{ref_str}

Context: {status_instruction}

Instructions:
- Write exactly 2-3 short, clear sentences.
- Use simple everyday words. Avoid all medical jargon.
- If the technical definition contains complex words, replace them with plain equivalents
  (e.g. "erythrocytes" → "red blood cells", "hepatic" → "liver").
- Do NOT start with "The reported value is..." — that is shown separately.
- Do NOT add disclaimers like "consult a doctor" more than once.
- Do NOT invent facts not present in the technical definition.
- Be warm and reassuring in tone.

Write the plain-language explanation now:"""

    return prompt


# ---------------------------------------------------------------------------
# Ollama API call
# ---------------------------------------------------------------------------


def _call_ollama(prompt: str) -> Optional[str]:
    """
    Send a prompt to the local Ollama server and return the response text.

    Returns None if Ollama is unavailable or returns an error.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,   # Low temperature for factual, consistent output
            "top_p": 0.9,
            "num_predict": 200,   # Limit output length (2-3 sentences is ~60-100 tokens)
        },
    }

    try:
        response = httpx.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("response", "").strip()
        return text if text else None

    except httpx.ConnectError:
        logger.warning(
            "Ollama server not reachable at %s. "
            "Make sure Ollama is running (`ollama serve`).",
            OLLAMA_BASE_URL,
        )
        return None
    except httpx.TimeoutException:
        logger.warning(
            "Ollama request timed out after %.0fs for model %s.",
            OLLAMA_TIMEOUT,
            OLLAMA_MODEL,
        )
        return None
    except Exception as exc:
        logger.warning("Ollama call failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def simplify_explanation(
    concept_name: str,
    technical_definition: str,
    value: Optional[Any] = None,
    unit: Optional[str] = None,
    reference_range: Optional[str] = None,
    status: str = "UNKNOWN",
) -> Optional[str]:
    """
    Return a plain-language explanation of a clinical concept for a patient.

    Checks the local cache first. If not cached, calls the local Ollama model.
    Caches the result for future calls.

    Parameters
    ----------
    concept_name         : Human-readable concept name (e.g. "Hemoglobin")
    technical_definition : Raw definition from BioPortal / Disease Ontology
    value                : Patient's measured value (numeric or string)
    unit                 : Unit of the measurement (e.g. "g/dL")
    reference_range      : Normal range string (e.g. "13.5 - 17.5")
    status               : "NORMAL", "HIGH", "LOW", or "UNKNOWN"

    Returns
    -------
    str  — plain-language explanation, or None if Ollama is unavailable.
    """
    if not OLLAMA_ENABLED:
        return None

    if not technical_definition or not technical_definition.strip():
        return None

    key = _cache_key(concept_name, status)

    # 1. Cache hit — return instantly
    with _cache_lock:
        if key in _memory_cache:
            logger.debug("Ollama cache hit for %r (%s)", concept_name, status)
            return _memory_cache[key]

    # 2. Cache miss — call Ollama
    logger.info(
        "Calling Ollama (%s) to simplify explanation for %r (status=%s)",
        OLLAMA_MODEL,
        concept_name,
        status,
    )
    prompt = _build_prompt(
        concept_name=concept_name,
        technical_definition=technical_definition,
        value=value,
        unit=unit,
        reference_range=reference_range,
        status=status,
    )
    simplified = _call_ollama(prompt)

    # 3. Cache and persist the result
    if simplified:
        with _cache_lock:
            _memory_cache[key] = simplified
            _save_cache(_memory_cache)
        logger.info(
            "Ollama simplified explanation cached for %r (%s)", concept_name, status
        )

    return simplified


def is_ollama_available() -> bool:
    """
    Quick health check — returns True if the Ollama server is reachable.
    Does NOT load a model, just checks the /api/tags endpoint.
    """
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        return response.status_code == 200
    except Exception:
        return False


def generate_report_summary(
    report_type: str,
    measurements: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> Optional[str]:
    """
    Generate an overall summary of the entire report in plain language.
    """
    if not OLLAMA_ENABLED:
        return None

    logger.info("Calling Ollama (%s) to generate report summary", OLLAMA_MODEL)
    
    # Build a concise representation of the report for the LLM
    findings_str = ""
    for f in findings:
        findings_str += f"- {f.get('concept')} (Assertion: {f.get('assertion')})\n"
        
    meas_str = ""
    abnormal_count = 0
    for m in measurements:
        val = m.get('value', 'N/A')
        unit = m.get('unit', '')
        ref = m.get('reference_range', 'N/A')
        alert_level = m.get("alert_level", "GREY")
        
        is_abnormal = alert_level in ("RED", "ORANGE", "YELLOW")
        status_label = "ABNORMAL" if is_abnormal else "NORMAL"
        
        if is_abnormal:
            abnormal_count += 1
            
        meas_str += f"- {m.get('concept')}: {val} {unit} (Range: {ref}) [{status_label}]\n"
        
    prompt = f"""You are a friendly medical report assistant helping a patient understand their overall {report_type.upper()} lab results.

Here are the key findings from the report:
{findings_str if findings_str else "None"}

Here are the measurements tested:
{meas_str if meas_str else "None"}

Instructions:
- Write exactly 2-4 short, clear sentences summarizing the overall health picture based on these results.
- Use simple everyday words. Avoid all medical jargon.
- Be warm and reassuring in tone.
- There are {abnormal_count} abnormal measurements.
- If everything is NORMAL (0 abnormal), say clearly that all results are within normal healthy ranges and no action is needed. Do NOT invent abnormalities.
- If there are ABNORMAL measurements, mention that some results are outside the normal range and suggest they discuss them with their doctor.
- Do NOT list the individual values or findings again. Just give the "big picture".

Write the overall plain-language summary now:"""

    simplified = _call_ollama(prompt)
    if simplified:
        logger.info("Ollama generated report summary successfully.")
    
    return simplified

