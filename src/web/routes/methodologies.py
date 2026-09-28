"""
Methodology and Model Plugins API routes for ClinRESET Web App.
Allows the user to inspect available backends, configure endpoints and API keys,
and execute live test sentences across backends directly from the UI.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from model_plugins import ModelSelector, extract_concepts_with_methodology
from src.extraction.model.grounding import GroundingValidator
from src.web.state import CONFIG_STATE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/methodologies", tags=["Methodologies"])


class ConfigureMethodologyRequest(BaseModel):
    active_backend: str
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None
    hf_token: Optional[str] = None
    hf_model: Optional[str] = None
    transformers_model: Optional[str] = None


class TestExtractionRequest(BaseModel):
    sentence: str
    backend: Optional[str] = None
    model_name: Optional[str] = None


@router.get("")
def get_methodologies_status() -> Dict[str, Any]:
    """Returns available backends, operational status, active configuration, and details."""
    availability = ModelSelector.list_available_backends()
    return {
        "active_backend": CONFIG_STATE.active_backend,
        "availability": availability,
        "config": CONFIG_STATE.to_dict(),
        "backend_descriptions": {
            "heuristic": "Pure deterministic grounded NLP engine. Offline, 0 memory, zero hallucination.",
            "ollama": "Local Ollama/LM Studio server. Fast 4-bit local weights (e.g. Qwen2.5:1.5b).",
            "hf_api": "Hugging Face Serverless Inference API. Zero local downloads, cloud-powered.",
            "transformers": "Local PyTorch / Transformers weights pipeline. Directly loaded in memory.",
        },
    }


@router.post("/configure")
def update_methodology_configuration(req: ConfigureMethodologyRequest) -> Dict[str, Any]:
    """Updates runtime backend selection and credentials from the UI."""
    valid_backends = list(ModelSelector.AVAILABLE_PLUGINS.keys())
    chosen = req.active_backend.lower().strip()

    if chosen not in valid_backends:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid backend '{chosen}'. Valid choices are: {valid_backends}",
        )

    CONFIG_STATE.active_backend = chosen

    if req.ollama_url:
        CONFIG_STATE.ollama_url = req.ollama_url.rstrip("/")
    if req.ollama_model:
        CONFIG_STATE.ollama_model = req.ollama_model.strip()

    if req.hf_token is not None and req.hf_token.strip():
        CONFIG_STATE.hf_token = req.hf_token.strip()
        os.environ["HUGGINGFACE_API_KEY"] = CONFIG_STATE.hf_token

    if req.hf_model:
        CONFIG_STATE.hf_model = req.hf_model.strip()

    if req.transformers_model:
        CONFIG_STATE.transformers_model = req.transformers_model.strip()

    # Also update environment variable
    os.environ["LLM_BACKEND"] = chosen

    logger.info(f"Updated runtime extraction methodology to: {chosen}")

    return {
        "status": "success",
        "message": f"Successfully updated methodology to '{chosen}'",
        "current_config": CONFIG_STATE.to_dict(),
        "availability": ModelSelector.list_available_backends(),
    }


@router.post("/test")
def test_concept_extraction(req: TestExtractionRequest) -> Dict[str, Any]:
    """
    Executes a test extraction on a clinical sentence using the specified or active backend.
    Measures latency and returns grounded concepts and assertions.
    """
    sentence = req.sentence.strip()
    if not sentence:
        raise HTTPException(status_code=400, detail="Sentence cannot be empty.")

    chosen_backend = req.backend or CONFIG_STATE.active_backend
    backend_kwargs = CONFIG_STATE.get_backend_kwargs()

    if req.model_name:
        backend_kwargs["model_name"] = req.model_name

    start_time = time.perf_counter()

    try:
        extracted = extract_concepts_with_methodology(
            sentence=sentence,
            methodology=chosen_backend,
            enforce_grounding=True,
            **backend_kwargs,
        )
    except Exception as e:
        logger.exception("Error during test extraction")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

    # Format results with grounding check
    results: List[Dict[str, Any]] = []
    for item in extracted:
        concept = item.get("concept", "")
        assertion = item.get("assertion", "PRESENT")
        is_grounded = GroundingValidator.is_grounded(concept, sentence)
        results.append({
            "concept": concept,
            "assertion": assertion,
            "is_grounded": is_grounded,
        })

    return {
        "backend_used": chosen_backend,
        "sentence": sentence,
        "elapsed_ms": elapsed_ms,
        "concepts_extracted": results,
        "count": len(results),
    }
