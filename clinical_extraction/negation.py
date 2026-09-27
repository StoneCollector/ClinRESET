"""
clinical_extraction/negation.py

Deterministic negation and assertion status detection.

Implements rule-based contextual detection for clinical assertions:
- PRESENT
- ABSENT  (negated = True)
- NORMAL
- POSSIBLE
- HISTORICAL
- UNKNOWN

Design rules
------------
- Strictly deterministic; no external model or API calls.
- Distinguishes 'No RWMA' (ABSENT) from 'RWMA' (PRESENT).
- Distinguishes 'Normal RV function' (NORMAL) from 'Abnormal RV function' (PRESENT).
- Correctly scopes negation to specific clauses, preventing negation leakage
  across commas, semicolons, bullets, and conjunctions.
- Preserves the original text of the finding.
"""

from __future__ import annotations

import re
from typing import Optional

from clinical_extraction.models import AssertionStatus


# ---------------------------------------------------------------------------
# Compiled regex patterns for negation and assertion cues
# ---------------------------------------------------------------------------

# Prefix negation cues: triggers ABSENT when appearing before the target
PREFIX_NEGATION_PATTERNS = [
    re.compile(r"\bno\s+evidence\s+of(?:\s+any)?\b", re.IGNORECASE),
    re.compile(r"\bno\s+sign\s+of\b", re.IGNORECASE),
    re.compile(r"\bno\s+definite\b", re.IGNORECASE),
    re.compile(r"\bno\s+significant\b", re.IGNORECASE),
    re.compile(r"\bnegative\s+for\b", re.IGNORECASE),
    re.compile(r"\bfree\s+of\b", re.IGNORECASE),
    re.compile(r"\brules?\s+out\b", re.IGNORECASE),
    re.compile(r"\bruled\s+out\b", re.IGNORECASE),
    re.compile(r"\bwithout(?:\s+any)?\b", re.IGNORECASE),
    re.compile(r"\bdenies\b", re.IGNORECASE),
    re.compile(r"\bdenied\b", re.IGNORECASE),
    re.compile(r"\babsent\b", re.IGNORECASE),
    re.compile(r"\bno\b", re.IGNORECASE),
    re.compile(r"\bnot\b", re.IGNORECASE),
    re.compile(r"\bnone\b", re.IGNORECASE),
    re.compile(r"\bnever\b", re.IGNORECASE),
]

# Suffix negation cues: triggers ABSENT when appearing after the target
SUFFIX_NEGATION_PATTERNS = [
    re.compile(r"\b(?:is\s+|was\s+)?not\s+seen\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+)?not\s+present\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+)?not\s+identified\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+)?not\s+detected\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+)?absent\b", re.IGNORECASE),
    re.compile(r"\b(?:is\s+|was\s+)?negative\b", re.IGNORECASE),
    re.compile(r"\bunremarkable\b", re.IGNORECASE),
]

# Normal assertion cues
NORMAL_PATTERNS = [
    re.compile(r"\bwithin\s+normal\s+limits\b", re.IGNORECASE),
    re.compile(r"\bwnl\b", re.IGNORECASE),
    re.compile(r"\bnormal\b", re.IGNORECASE),
    re.compile(r"\bintact\b", re.IGNORECASE),
    re.compile(r"\bopens?\s+well\b", re.IGNORECASE),
    re.compile(r"\bopening\s+well\b", re.IGNORECASE),
    re.compile(r"\bpreserved\b", re.IGNORECASE),
    re.compile(r"\badequate\b", re.IGNORECASE),
]

# Possible / uncertainty cues
POSSIBLE_PATTERNS = [
    re.compile(r"\bpossible\b", re.IGNORECASE),
    re.compile(r"\bpossibly\b", re.IGNORECASE),
    re.compile(r"\bprobable\b", re.IGNORECASE),
    re.compile(r"\bprobably\b", re.IGNORECASE),
    re.compile(r"\bsuspected\b", re.IGNORECASE),
    re.compile(r"\bsuspicious\s+for\b", re.IGNORECASE),
    re.compile(r"\bcannot\s+rule\s+out\b", re.IGNORECASE),
    re.compile(r"\bcannot\s+be\s+excluded\b", re.IGNORECASE),
    re.compile(r"\bequivocal\b", re.IGNORECASE),
    re.compile(r"\bborderline\b", re.IGNORECASE),
    re.compile(r"\blikely\b", re.IGNORECASE),
]

# Historical assertion cues
HISTORICAL_PATTERNS = [
    re.compile(r"\bhistory\s+of\b", re.IGNORECASE),
    re.compile(r"\bh/o\b", re.IGNORECASE),
    re.compile(r"\bpast\s+medical\s+history\b", re.IGNORECASE),
    re.compile(r"\bpmh\b", re.IGNORECASE),
    re.compile(r"\bprior\b", re.IGNORECASE),
    re.compile(r"\bprevious\b", re.IGNORECASE),
    re.compile(r"\bstatus\s+post\b", re.IGNORECASE),
    re.compile(r"\bs/p\b", re.IGNORECASE),
]

# Clause boundary separators for splitting compound sentences
CLAUSE_DELIMITERS = re.compile(
    r"(?:(?<=[.!?])\s+|[;\n\r]+|\s*[-–—•*]\s*|\s*,\s*(?=(?:no|not|normal|with|without|mild|moderate|severe|grade)\b))",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def split_into_clauses(text: str) -> list[str]:
    """
    Split complex clinical sentences or section texts into distinct clauses.

    Prevents negation or assertion bleeding across independent phrases
    (e.g. "Conc LVH, No RWMA" -> ["Conc LVH", "No RWMA"]).
    """
    if not text:
        return []

    # Strip markdown formatting markers
    cleaned = re.sub(r"[*_~`#]", " ", text)
    # Normalize excessive whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    raw_clauses = CLAUSE_DELIMITERS.split(cleaned)
    clauses: list[str] = []

    for c in raw_clauses:
        chunk = c.strip(" ,.-;")
        if chunk:
            clauses.append(chunk)

    return clauses if clauses else [cleaned]


def detect_assertion(
    text: str,
    target: Optional[str] = None,
) -> tuple[str, bool]:
    """
    Determine the assertion status and negation flag for text or target within text.

    Parameters
    ----------
    text:
        The clause, sentence, or source text to evaluate.
    target:
        Optional specific entity term within the text to focus the scope on.
        If None, the entire text snippet is evaluated.

    Returns
    -------
    tuple[str, bool]
        (assertion_status, is_negated)
        Where assertion_status is one of AssertionStatus.ALL
        and is_negated is a boolean.
    """
    status, is_negated, _ = detect_assertion_with_cue(text, target)
    return status, is_negated


def detect_assertion_with_cue(
    text: str,
    target: Optional[str] = None,
) -> tuple[str, bool, Optional[str]]:
    """
    Determine assertion status, negation flag, and matching cue pattern.

    Parameters
    ----------
    text:
        Source context string.
    target:
        Optional entity term within text.

    Returns
    -------
    tuple[str, bool, Optional[str]]
        (assertion_status, is_negated, matched_cue)
    """
    if not text:
        return AssertionStatus.UNKNOWN, False, None

    # Determine scope: if target is provided and present in text, extract window
    scope_before = text
    scope_after = ""

    if target:
        # Case-insensitive search for target
        idx = text.lower().find(target.lower())
        if idx != -1:
            scope_before = text[:idx]
            scope_after = text[idx + len(target):]

    # 1. Check for Historical cues
    for pat in HISTORICAL_PATTERNS:
        match = pat.search(scope_before)
        if match:
            return AssertionStatus.HISTORICAL, False, match.group(0)

    # 2. Check for Negation (ABSENT)
    # Check prefix negation (before target)
    for pat in PREFIX_NEGATION_PATTERNS:
        match = pat.search(scope_before)
        if match:
            # Verify no intervening contrastive conjunction (e.g. "but", "however")
            post_cue = scope_before[match.end():]
            if not re.search(r"\b(?:but|however|although|nevertheless)\b", post_cue, re.IGNORECASE):
                return AssertionStatus.ABSENT, True, match.group(0)

    # Check suffix negation (after target)
    if scope_after:
        for pat in SUFFIX_NEGATION_PATTERNS:
            match = pat.search(scope_after)
            if match:
                return AssertionStatus.ABSENT, True, match.group(0)

    # If the text itself starts with negation words (when target is the whole text or None)
    for pat in PREFIX_NEGATION_PATTERNS:
        match = pat.search(text)
        if match and match.start() <= 5:  # At or very near the beginning
            return AssertionStatus.ABSENT, True, match.group(0)

    # 3. Check for Normal cues (NORMAL)
    for pat in NORMAL_PATTERNS:
        match = pat.search(text)
        if match:
            # Ensure "normal" is not negated (e.g. "not normal")
            pre_normal = text[:match.start()]
            if not any(np.search(pre_normal) for np in PREFIX_NEGATION_PATTERNS):
                return AssertionStatus.NORMAL, False, match.group(0)

    # 4. Check for Possible / Uncertainty cues (POSSIBLE)
    for pat in POSSIBLE_PATTERNS:
        match = pat.search(text)
        if match:
            return AssertionStatus.POSSIBLE, False, match.group(0)

    # 5. Default is PRESENT
    return AssertionStatus.PRESENT, False, None
