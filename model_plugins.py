"""
ClinRESET Model Plugins and Methodology Selector CLI & API.

Enables seamless switching between 4 concept extraction methodologies:
1. 'heuristic'   : Pure deterministic grounded clinical NLP (offline, instant, 0 dependencies).
2. 'ollama'      : Local Ollama / LM Studio (e.g. Qwen2.5:1.5b, Llama-3.2:1b).
3. 'hf_api'      : Hugging Face Serverless Inference API (0 local downloads, cloud-powered).
4. 'transformers': Local PyTorch / Transformers weights (running Qwen2.5-1.5B locally).

Usage:
    # Python API:
    from model_plugins import ModelSelector, extract_concepts_with_methodology
    results = extract_concepts_with_methodology("Liver: is enlarged (~15.8cm)", methodology="heuristic")

    # Command line:
    python model_plugins.py --list
    python model_plugins.py --backend heuristic --sentence "Mild cardiomegaly noted, no pneumothorax."
    python model_plugins.py --compare --sentence "Grade 1 diastolic dysfunction, no pericardial effusion."
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.extraction.model.grounding import GroundingValidator
from src.extraction.model.model_plugins import (
    BaseModelPlugin,
    HeuristicPlugin,
    HuggingFaceApiPlugin,
    ModelSelector,
    OllamaPlugin,
    TransformersPlugin,
)

logger = logging.getLogger("model_plugins")

__all__ = [
    "BaseModelPlugin",
    "HeuristicPlugin",
    "OllamaPlugin",
    "HuggingFaceApiPlugin",
    "TransformersPlugin",
    "ModelSelector",
    "extract_concepts_with_methodology",
]


def extract_concepts_with_methodology(
    sentence: str,
    methodology: Optional[str] = None,
    enforce_grounding: bool = True,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    Convenience function to extract concepts using any chosen methodology.

    Args:
        sentence: Raw clinical clause or sentence.
        methodology: 'heuristic', 'ollama', 'hf_api', 'transformers', or None (auto-detect).
        enforce_grounding: If True (default), strictly purges ungrounded hallucinations.
        **kwargs: Additional options (e.g. model_name, api_token, base_url).

    Returns:
        List of dicts: [{'concept': '...', 'assertion': 'PRESENT|ABSENT|NORMAL'}]
    """
    if not sentence or not sentence.strip():
        return []

    backend = ModelSelector.get_backend(backend_name=methodology, **kwargs)
    raw_items = backend.extract(sentence)

    if enforce_grounding:
        return GroundingValidator.filter_items(raw_items, sentence)
    return raw_items


def format_status_table() -> str:
    """Formats a diagnostic table showing the availability status of all 4 methodologies."""
    status = ModelSelector.list_available_backends()
    lines = [
        "ClinRESET Concept Extraction Methodologies Status:",
        "-------------------------------------------------------------------------",
        f"  1. [heuristic]    : {'[ACTIVE / AVAILABLE]' if status.get('heuristic') else '[OFFLINE]'}",
        "     Fast, rule-based clinical NLP. Offline, 0 memory, zero hallucination.",
        f"  2. [ollama]       : {'[ACTIVE / DETECTED]' if status.get('ollama') else '[OFFLINE / NOT RUNNING]'}",
        "     Local Ollama/LM Studio server. Fast 4-bit GGUF (e.g. `ollama run qwen2.5:1.5b`).",
        f"  3. [hf_api]       : {'[ACTIVE / TOKEN FOUND]' if status.get('hf_api') else '[OFFLINE / NO TOKEN]'}",
        "     Hugging Face Serverless API (set HUGGINGFACE_API_KEY in .env or environment).",
        f"  4. [transformers] : {'[ACTIVE / INSTALLED]' if status.get('transformers') else '[OFFLINE / NOT INSTALLED]'}",
        "     Local PyTorch/Transformers pipeline (requires `pip install torch transformers`).",
        "-------------------------------------------------------------------------",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="ClinRESET Model Plugins & Methodology Selector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python model_plugins.py --list
  python model_plugins.py --backend heuristic --sentence "Liver: is enlarged (~15.8cm), normal in outline."
  python model_plugins.py --compare --sentence "Loss of lumbar lordosis, no disc bulge."
  python model_plugins.py --backend ollama --sentence "Lung feilds are clear." --model qwen2.5:1.5b
        """,
    )
    parser.add_argument("--list", action="store_true", help="List all methodologies and their readiness status.")
    parser.add_argument(
        "--backend",
        "-b",
        choices=["heuristic", "ollama", "hf_api", "transformers"],
        default=None,
        help="Select extraction methodology to use.",
    )
    parser.add_argument(
        "--sentence",
        "-s",
        type=str,
        default="Liver is enlarged in size (~15.8cm), normal in outline; no focal lesion is seen.",
        help="Clinical sentence to extract concepts and assertions from.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run the test sentence across all available backends and compare outputs.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="Qwen/Qwen2.5-1.5B-Instruct",
        help="Model identifier for LLM backends (default: Qwen/Qwen2.5-1.5B-Instruct).",
    )
    parser.add_argument(
        "--no-grounding",
        action="store_true",
        help="Disable GroundingValidator hallucination filtering (raw model outputs).",
    )

    args = parser.parse_args()

    if args.list:
        print("\n" + format_status_table())
        return

    enforce = not args.no_grounding

    if args.compare:
        print("\n" + "=" * 70)
        print("ClinRESET Methodology Comparison")
        print("=" * 70)
        print(f"Target Sentence:\n  \"{args.sentence}\"\n")
        status = ModelSelector.list_available_backends()

        for backend_name in ["heuristic", "ollama", "hf_api", "transformers"]:
            is_avail = status.get(backend_name, False)
            avail_str = "AVAILABLE" if is_avail else "NOT READY (fallback used)"
            print(f"--- Methodology: [{backend_name.upper()}] ({avail_str}) ---")
            try:
                extracted = extract_concepts_with_methodology(
                    sentence=args.sentence,
                    methodology=backend_name,
                    enforce_grounding=enforce,
                    model_name=args.model,
                )
                if not extracted:
                    print("  No concepts extracted.")
                for item in extracted:
                    concept = item.get("concept", "")
                    assertion = item.get("assertion", "PRESENT")
                    grounded = GroundingValidator.is_grounded(concept, args.sentence)
                    ground_flag = "[GROUNDED]" if grounded else "[UNGROUNDED!]"
                    print(f"  * {concept:<30} | {assertion:<8} {ground_flag}")
            except Exception as e:
                print(f"  Error running {backend_name}: {e}")
            print()
        return

    # Single backend execution
    chosen = args.backend or os.environ.get("LLM_BACKEND") or "heuristic"
    print(f"\n[ClinRESET Extractor] Running methodology: '{chosen}'")
    print(f"Input: \"{args.sentence}\"\n")

    results = extract_concepts_with_methodology(
        sentence=args.sentence,
        methodology=chosen,
        enforce_grounding=enforce,
        model_name=args.model,
    )

    print(f"Extracted ({len(results)} concepts):")
    for r in results:
        concept = r.get("concept", "")
        assertion = r.get("assertion", "")
        grounded = GroundingValidator.is_grounded(concept, args.sentence)
        status_flag = "[GROUNDED]" if grounded else "[UNGROUNDED!]"
        print(f"  - Concept:   {concept:<25} | Assertion: {assertion:<8} | {status_flag}")
    print()


if __name__ == "__main__":
    main()
