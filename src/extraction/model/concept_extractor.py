"""
Concept Extractor for clinical clauses.
Integrates small language models (Qwen2.5-1.5B) and grounded NLP concept extraction.
Always enforces GroundingValidator to eliminate hallucinations.
"""

import logging
from typing import List, Dict, Any, Optional

from .grounding import GroundingValidator
from .model_plugins import ModelSelector, BaseModelPlugin, HeuristicPlugin

logger = logging.getLogger(__name__)


class ConceptExtractor:
    """Extracts grounded finding concepts and assertions from clinical sentences."""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
        use_local_weights: bool = False,
        backend: Optional[str] = None,
        **backend_kwargs,
    ):
        self.model_name = model_name
        self.use_local_weights = use_local_weights

        if use_local_weights and not backend:
            backend = "transformers"

        self.backend_name = backend
        self.plugin: BaseModelPlugin = ModelSelector.get_backend(
            backend_name=self.backend_name,
            model_name=self.model_name,
            **backend_kwargs,
        )

    def extract_concepts(self, sentence: str) -> List[Dict[str, Any]]:
        """
        Extracts list of {"concept": "...", "assertion": "PRESENT|ABSENT|NORMAL"} from sentence.
        Applies GroundingValidator to guarantee zero hallucinations.
        """
        if not sentence or not sentence.strip():
            return []

        raw_items = self.plugin.extract(sentence)
        return GroundingValidator.filter_items(raw_items, sentence)

    @classmethod
    def _extract_grounded_heuristic(cls, sentence: str) -> List[Dict[str, Any]]:
        """High-precision grounded parser delegating to HeuristicPlugin."""
        return HeuristicPlugin().extract(sentence)

    @classmethod
    def _clean_finding_term(cls, text: str) -> Optional[str]:
        """Term cleaner delegating to HeuristicPlugin."""
        return HeuristicPlugin._clean_finding_term(text)
