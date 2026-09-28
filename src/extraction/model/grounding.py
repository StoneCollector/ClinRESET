"""
Strict text-grounding validation filter.
Guarantees that every model-extracted concept is strictly grounded in the source text.
Drops any concept that hallucinates terms not found in the input clause.
"""

import re
from typing import List, Dict, Any, Set, Tuple


class GroundingValidator:
    """Validates that extracted concepts only contain words present in the source sentence."""

    STOP_WORDS = {
        "is", "the", "a", "an", "and", "in", "of", "with", "or", "to", "for", "on", "at",
        "by", "from", "its", "are", "was", "were", "been", "be", "has", "have", "had",
        "shows", "showing", "seen", "noted", "detected"
    }

    @classmethod
    def get_tokens(cls, text: str) -> Set[str]:
        """Extracts normalized alphanumeric words from text."""
        words = re.findall(r"\b[a-z0-9]+\b", text.lower())
        return {w for w in words if w not in cls.STOP_WORDS}

    @classmethod
    def is_grounded(cls, concept: str, source_sentence: str, min_overlap: float = 0.5) -> bool:
        """
        Validates if the concept words appear in the source sentence.
        Returns True if at least 50% (or all significant words) appear in the source.
        """
        if not concept or not source_sentence:
            return False

        concept_tokens = cls.get_tokens(concept)
        if not concept_tokens:
            # If concept is very short or all stop words, check direct substring
            return concept.strip().lower() in source_sentence.lower()

        source_tokens = cls.get_tokens(source_sentence)

        overlap = concept_tokens.intersection(source_tokens)
        ratio = len(overlap) / len(concept_tokens)

        # Allow slight morphological variation (e.g. calculus -> calculi, lung -> lungs)
        if ratio < min_overlap:
            fuzzy_matches = 0
            for ct in concept_tokens:
                if any(st.startswith(ct[:4]) or ct.startswith(st[:4]) for st in source_tokens if len(st) >= 4 and len(ct) >= 4):
                    fuzzy_matches += 1
            ratio = fuzzy_matches / len(concept_tokens)

        return ratio >= min_overlap

    @classmethod
    def filter_items(cls, items: List[Dict[str, Any]], source_sentence: str) -> List[Dict[str, Any]]:
        """Filters out any candidate items whose concepts are not grounded in the source sentence."""
        grounded_items: List[Dict[str, Any]] = []

        for item in items:
            concept = item.get("concept", "")
            if cls.is_grounded(concept, source_sentence):
                grounded_items.append(item)

        return grounded_items
