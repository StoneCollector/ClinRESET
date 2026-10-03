"""
clinical_explanation/config.py

Configuration for the clinical explanation API fallback layer.

The BioPortal API key is stored here so it is kept out of the core logic
files and can be changed in one place.

BioPortal account & key: https://bioportal.bioontology.org/account
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# BioPortal API key
# ---------------------------------------------------------------------------
# Set to an empty string "" to disable BioPortal lookups entirely.
# When disabled, the system will still use Disease Ontology as a fallback.
BIOPORTAL_API_KEY: str = "af548872-6ec5-4a01-ad1c-0ac124a22808"


# ---------------------------------------------------------------------------
# Ollama local LLM configuration
# ---------------------------------------------------------------------------
# URL of the local Ollama server (default: http://localhost:11434)
OLLAMA_BASE_URL: str = "http://localhost:11434"

# Model to use for plain-language simplification.
# Must be pulled locally: ollama pull mistral
OLLAMA_MODEL: str = "mistral:latest"

# Set to False to disable Ollama and always use the raw technical definition.
OLLAMA_ENABLED: bool = True

# Seconds to wait for a response before giving up and falling back.
OLLAMA_TIMEOUT: float = 120.0
