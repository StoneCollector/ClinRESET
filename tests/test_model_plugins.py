"""
Tests for Model Plugins and Methodology Selector.
Verifies switching between backends, graceful fallbacks, and grounding validation.
"""

import os
import pytest
from src.extraction.model.model_plugins import (
    BaseModelPlugin,
    HeuristicPlugin,
    OllamaPlugin,
    HuggingFaceApiPlugin,
    TransformersPlugin,
    ModelSelector,
)
from src.extraction.model.concept_extractor import ConceptExtractor
from model_plugins import extract_concepts_with_methodology


def test_list_available_backends():
    status = ModelSelector.list_available_backends()
    assert "heuristic" in status
    assert "ollama" in status
    assert "hf_api" in status
    assert "transformers" in status
    assert status["heuristic"] is True


def test_get_backend_explicit():
    # Heuristic
    h = ModelSelector.get_backend("heuristic")
    assert isinstance(h, HeuristicPlugin)
    assert h.name == "heuristic"

    # Ollama
    o = ModelSelector.get_backend("ollama")
    assert isinstance(o, OllamaPlugin)
    assert o.name == "ollama"

    # HF API
    hf = ModelSelector.get_backend("hf_api")
    assert isinstance(hf, HuggingFaceApiPlugin)
    assert hf.name == "hf_api"

    # Transformers
    t = ModelSelector.get_backend("transformers")
    assert isinstance(t, TransformersPlugin)
    assert t.name == "transformers"


def test_get_backend_unknown_fallback():
    # An unknown backend should log a warning and fall back to heuristic
    b = ModelSelector.get_backend("non_existent_engine")
    assert isinstance(b, HeuristicPlugin)


def test_get_backend_env_var(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "heuristic")
    b = ModelSelector.get_backend()
    assert isinstance(b, HeuristicPlugin)


def test_heuristic_extraction():
    plugin = HeuristicPlugin()
    sentence = "Loss of lumbar lordosis, no disc bulge."
    items = plugin.extract(sentence)
    assert len(items) == 2

    concepts = {item["concept"].lower(): item["assertion"] for item in items}
    assert "disc bulge" in concepts
    assert concepts["disc bulge"] == "ABSENT"


def test_extract_concepts_with_methodology_wrapper():
    sentence = "No pericardial effusion is seen."
    results = extract_concepts_with_methodology(sentence, methodology="heuristic")
    assert len(results) == 1
    assert "pericardial effusion" in results[0]["concept"].lower()
    assert results[0]["assertion"] == "ABSENT"


def test_concept_extractor_with_backend_param():
    extractor = ConceptExtractor(backend="heuristic")
    sentence = "Mild cardiomegaly noted, no focal consolidation."
    results = extractor.extract_concepts(sentence)
    assert len(results) >= 1
