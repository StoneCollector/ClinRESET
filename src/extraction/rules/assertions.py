"""
Deterministic assertion classification rules.
Categorizes findings into PRESENT, ABSENT, or NORMAL using high-precision lexical cues.
"""

import re
from typing import Optional

# Prefix negation patterns
PREFIX_NEGATION = [
    re.compile(r"\bno\s+evidence\s+of(?:\s+any)?\b", re.IGNORECASE),
    re.compile(r"\bno\s+e/o\b", re.IGNORECASE),
    re.compile(r"\bno\s+sign\s+of\b", re.IGNORECASE),
    re.compile(r"\bnegative\s+for\b", re.IGNORECASE),
    re.compile(r"\bfree\s+of\b", re.IGNORECASE),
    re.compile(r"\bwithout(?:\s+any)?\b", re.IGNORECASE),
    re.compile(r"\brules?\s+out\b", re.IGNORECASE),
    re.compile(r"\bruled\s+out\b", re.IGNORECASE),
    re.compile(r"\bdenies\b", re.IGNORECASE),
    re.compile(r"\bdenied\b", re.IGNORECASE),
    re.compile(r"\babsent\b", re.IGNORECASE),
    re.compile(r"\bno\b", re.IGNORECASE),
    re.compile(r"\bnot\b", re.IGNORECASE),
    re.compile(r"\bnone\b", re.IGNORECASE),
    re.compile(r"\bnil\b", re.IGNORECASE),
]

# Suffix negation patterns
SUFFIX_NEGATION = [
    re.compile(r"\b(?:is\s+|was\s+|are\s+)?not\s+seen\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+|are\s+)?not\s+present\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+|are\s+)?not\s+identified\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+|are\s+)?not\s+detected\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+|are\s+)?not\s+noted\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+|are\s+)?not\s+dilated\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+|are\s+)?absent\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+|are\s+)?negative\b", re.IGNORECASE),
]

# Normalcy patterns
NORMAL_PATTERNS = [
    re.compile(r"\bwithin\s+normal\s+limits\b", re.IGNORECASE),
    re.compile(r"\bwnl\b", re.IGNORECASE),
    re.compile(r"\bnormal\b", re.IGNORECASE),
    re.compile(r"\bintact\b", re.IGNORECASE),
    re.compile(r"\bclear\b", re.IGNORECASE),
    re.compile(r"\bunremarkable\b", re.IGNORECASE),
    re.compile(r"\bopening\s+well\b", re.IGNORECASE),
    re.compile(r"\bopens\s+well\b", re.IGNORECASE),
    re.compile(r"\bpreserved\b", re.IGNORECASE),
    re.compile(r"\bmaintained\b", re.IGNORECASE),
    re.compile(r"\bcentral\b", re.IGNORECASE),
    re.compile(r"\bin\s+midline\b", re.IGNORECASE),
]


class AssertionClassifier:
    """Classifies clinical assertion status deterministically."""

    @classmethod
    def classify(cls, text: str) -> str:
        """
        Determines if the clause represents:
        - 'ABSENT': Finding explicitly negated ('No focal lesion seen')
        - 'NORMAL': Anatomical structure stated as normal/clear/unremarkable ('Lung fields are clear')
        - 'PRESENT': Finding observed/present ('Grade II fatty liver')
        """
        clean = text.strip()

        # Check for explicit negation first
        has_negation = False
        for pat in PREFIX_NEGATION:
            if pat.search(clean):
                has_negation = True
                break

        if not has_negation:
            for pat in SUFFIX_NEGATION:
                if pat.search(clean):
                    has_negation = True
                    break

        if has_negation:
            # Special case: "not normal" or "no normal" -> NOT absent, it is PRESENT / abnormal
            if re.search(r"\b(?:not|no)\s+normal\b", clean, re.IGNORECASE):
                return "PRESENT"
            return "ABSENT"

        # Check for normalcy cues
        for pat in NORMAL_PATTERNS:
            if pat.search(clean):
                return "NORMAL"

        return "PRESENT"
