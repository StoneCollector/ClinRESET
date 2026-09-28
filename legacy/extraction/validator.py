"""
Extraction validator.

Every extraction result passes through this module before the
pipeline decides whether to use the result or fall back to the
next extractor.

Returns one of:
    "GOOD"      — result is trustworthy
    "DEGRADED"  — result is partially usable; pipeline may still fall back
    "FAILED"    — result is not usable; pipeline must fall back

Design principles
-----------------
- The validator is generic: it does not hard-code expectations for a
  specific medical report type.
- Multiple independent checks are run and their scores are aggregated.
- A single character-count threshold is NOT the entire validation
  mechanism.
- Structural coherence is checked: headings, table syntax, measurement
  relationship plausibility.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Absolute minimum character count to consider the extraction non-empty.
_ABSOLUTE_MIN_CHARS = 50

# Fraction of non-printable / garbage characters above which text is
# considered corrupt.
_GARBAGE_CHAR_FRACTION_THRESHOLD = 0.30

# Minimum expected unique words for a "meaningful" extraction.
_MIN_UNIQUE_WORDS = 10

# Minimum number of meaningful lines.
_MIN_LINES = 3

# Score thresholds for GOOD / DEGRADED / FAILED.
_SCORE_GOOD = 0.70
_SCORE_DEGRADED = 0.40


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def _check_non_empty(text: str) -> tuple[float, str | None]:
    """Fail immediately if the text is below the absolute minimum."""
    if len(text.strip()) < _ABSOLUTE_MIN_CHARS:
        return 0.0, f"Text too short ({len(text.strip())} chars < {_ABSOLUTE_MIN_CHARS})"
    return 1.0, None


def _check_garbage_ratio(text: str) -> tuple[float, str | None]:
    """
    Detect a high proportion of non-printable / control characters.
    Unicode text with accented characters or currency symbols is fine;
    only true control characters and replacement characters are penalised.
    """
    if not text:
        return 0.0, "Empty text"

    garbage = sum(
        1
        for ch in text
        if (
            (ord(ch) < 32 and ch not in "\n\r\t")
            or ch == "\ufffd"
        )
    )
    ratio = garbage / len(text)
    if ratio > _GARBAGE_CHAR_FRACTION_THRESHOLD:
        return 0.0, f"High garbage character ratio: {ratio:.1%}"
    # Partial penalty for moderate garbage.
    if ratio > 0.05:
        return 0.5, f"Moderate garbage character ratio: {ratio:.1%}"
    return 1.0, None


def _check_meaningful_words(text: str) -> tuple[float, str | None]:
    """Check that the text contains a minimum number of distinct words."""
    words = re.findall(r"[A-Za-z]{2,}", text)
    unique = set(w.lower() for w in words)
    if len(unique) < _MIN_UNIQUE_WORDS:
        return 0.0, f"Too few unique words ({len(unique)} < {_MIN_UNIQUE_WORDS})"
    return 1.0, None


def _check_line_count(text: str) -> tuple[float, str | None]:
    """Check that the extraction has a reasonable number of non-blank lines."""
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < _MIN_LINES:
        return 0.5, f"Very few non-blank lines ({len(lines)} < {_MIN_LINES})"
    return 1.0, None


def _check_table_coherence(text: str) -> tuple[float, str | None]:
    """
    When Markdown pipe-tables are present, verify that rows have a
    consistent column count and that the separator row is well-formed.

    Returns a score of 1.0 if no tables are found (not penalised) or
    if the tables found are structurally coherent.
    """
    table_rows = [l for l in text.splitlines() if l.strip().startswith("|")]

    if not table_rows:
        return 1.0, None  # No tables to validate — not a failure.

    # Split tables on blank lines between them.
    col_counts: list[int] = []
    broken_rows = 0

    for row in table_rows:
        # Skip separator rows.
        if re.match(r"^\|[\s\-:|]+\|", row):
            continue
        cells = [c.strip() for c in row.strip("|").split("|")]
        col_counts.append(len(cells))

    if not col_counts:
        return 1.0, None

    majority_cols = max(set(col_counts), key=col_counts.count)
    broken_rows = sum(1 for c in col_counts if c != majority_cols)
    broken_fraction = broken_rows / len(col_counts) if col_counts else 0.0

    if broken_fraction > 0.5:
        return 0.3, f"Table structure is inconsistent ({broken_rows}/{len(col_counts)} rows have wrong column count)"
    if broken_fraction >= 0.15:
        return 0.7, f"Minor table inconsistencies ({broken_rows}/{len(col_counts)} rows)"

    return 1.0, None


def _check_heading_preservation(text: str) -> tuple[float, str | None]:
    """
    Check that at least some heading-like content is present.

    Headings in Markdown start with '#'.  In plain-text extractions,
    they are typically ALL-CAPS lines.  Either is acceptable.
    """
    markdown_headings = re.findall(r"^#{1,6}\s+\S", text, re.MULTILINE)
    allcaps_headings = re.findall(r"^[A-Z][A-Z\s\-/]{4,}$", text, re.MULTILINE)

    if markdown_headings or allcaps_headings:
        return 1.0, None

    # Not a hard failure — some reports have no formal headings.
    return 0.8, "No recognisable headings found (Markdown or ALL-CAPS)."


def _check_measurement_plausibility(text: str) -> tuple[float, str | None]:
    """
    Check that numeric values plausibly resembling measurements are
    present in the text.

    This does NOT interpret whether measurements are normal or abnormal.
    It merely checks that numbers (possibly with units) exist.
    """
    # Match patterns like: 60%, 32.5%, 23mm, 1.47 m/s, (55-74%), 20-37mm
    measurement_pattern = re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:%|mm|cm|m/s|mmhg|l|mg|dl|g|iu|u/l)?\b",
        re.IGNORECASE,
    )
    hits = measurement_pattern.findall(text)
    if len(hits) == 0:
        # Not all medical documents have measurements (e.g. radiology narrative).
        return 0.8, "No numeric measurement patterns detected."
    return 1.0, None


# ---------------------------------------------------------------------------
# Aggregate validator
# ---------------------------------------------------------------------------


@dataclass
class ValidationDetail:
    check_name: str
    score: float
    warning: str | None = None


def validate_extraction(text: str, context: str = "") -> tuple[str, list[str], dict]:
    """
    Validate an extraction result.

    Parameters
    ----------
    text:
        The extracted text or Markdown to validate.
    context:
        Optional label for logging (e.g. the extractor name).

    Returns
    -------
    status:
        "GOOD" | "DEGRADED" | "FAILED"
    warnings:
        List of warning messages.
    scores:
        Dict mapping check name → score (0.0–1.0).
    """

    checks = [
        ("non_empty", _check_non_empty),
        ("garbage_ratio", _check_garbage_ratio),
        ("meaningful_words", _check_meaningful_words),
        ("line_count", _check_line_count),
        ("table_coherence", _check_table_coherence),
        ("heading_preservation", _check_heading_preservation),
        ("measurement_plausibility", _check_measurement_plausibility),
    ]

    details: list[ValidationDetail] = []
    warnings: list[str] = []
    scores: dict[str, float] = {}

    for name, fn in checks:
        score, warning = fn(text)
        details.append(ValidationDetail(check_name=name, score=score, warning=warning))
        scores[name] = score
        if warning:
            warnings.append(f"[{name}] {warning}")

    # Hard-fail on critical checks.
    if scores["non_empty"] == 0.0 or scores["garbage_ratio"] == 0.0:
        logger.warning(
            "Extraction %s: hard FAILED (non_empty=%.2f, garbage_ratio=%.2f)",
            context,
            scores["non_empty"],
            scores["garbage_ratio"],
        )
        return "FAILED", warnings, scores

    # Weighted average of remaining checks.
    weights = {
        "non_empty": 2.0,
        "garbage_ratio": 2.0,
        "meaningful_words": 1.5,
        "line_count": 1.0,
        "table_coherence": 1.5,
        "heading_preservation": 0.5,
        "measurement_plausibility": 0.5,
    }

    weighted_sum = sum(scores[n] * weights[n] for n in scores)
    total_weight = sum(weights.values())
    aggregate = weighted_sum / total_weight

    if aggregate >= _SCORE_GOOD:
        status = "GOOD"
    elif aggregate >= _SCORE_DEGRADED:
        status = "DEGRADED"
    else:
        status = "FAILED"

    logger.info(
        "Validation %s: status=%s aggregate=%.3f",
        context,
        status,
        aggregate,
    )
    scores["_aggregate"] = round(aggregate, 4)

    return status, warnings, scores
