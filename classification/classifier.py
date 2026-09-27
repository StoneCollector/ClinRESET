"""
classification/classifier.py

Weighted-signature report type classifier.

Architecture
------------

    ExtractionResult
         ↓
    signal_extractor   →   list[SignalCandidate]
         ↓
    _score_signature   →   (raw_score, evidence_list)   ← per signature
         ↓
    _normalise_scores  →   confidence values
         ↓
    _decide            →   ClassificationResult

The classifier is deliberately free of any report-type knowledge.
All medical vocabulary and weights live in signatures.py.

Confidence / status logic
--------------------------
  CONFIDENT  — top_score >= CONFIDENCE_THRESHOLD AND
               top_score > second_score * AMBIGUITY_SEPARATION_FACTOR
  UNCERTAIN  — top_score >= MIN_VIABLE_SCORE AND NOT confident
  AMBIGUOUS  — two or more signatures score within AMBIGUITY_GAP of each other
               AND top_score >= MIN_VIABLE_SCORE
  UNKNOWN    — no signature reached MIN_VIABLE_SCORE

These thresholds are module-level constants so they can be tuned without
touching classifier logic.

No ML, no embeddings, no external APIs — rule-based only.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from classification.models import ClassificationResult, Evidence, Alternative
from classification.signal_extractor import SignalCandidate, extract_signals
from classification.signatures import (
    ALL_SIGNATURES,
    ReportSignature,
    SignalGroup,
    TITLE_WEIGHT,
    SECTION_TITLE_WEIGHT,
    TABLE_TITLE_WEIGHT,
    MEASUREMENT_NAME_WEIGHT,
    EXCLUSION_PENALTY,
)
from extraction.models import ExtractionResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

# A candidate must reach at least this raw score to be considered viable.
MIN_VIABLE_SCORE: float = 5.0

# Raw score at which we consider the classification CONFIDENT.
CONFIDENCE_THRESHOLD: float = 12.0

# The top candidate must be this many times the score of the second
# candidate to be considered unambiguous.
AMBIGUITY_SEPARATION_FACTOR: float = 1.4

# If two candidates are within this fraction of the top score, call it AMBIGUOUS.
AMBIGUITY_GAP_FRACTION: float = 0.25

# Maximum raw score used for confidence normalisation.
# Chosen so that a clean title match + a few strong signals → confidence ≈ 0.9+.
NORMALISATION_CEILING: float = 35.0


# ---------------------------------------------------------------------------
# Source-field base weights
# (applied to structured field signals before keyword-group weights)
# ---------------------------------------------------------------------------

_SOURCE_BASE_WEIGHTS: dict[str, float] = {
    "document_title": TITLE_WEIGHT,
    "section_title": SECTION_TITLE_WEIGHT,
    "table_title": TABLE_TITLE_WEIGHT,
    "table_header": 4.0,
    "measurement_name": MEASUREMENT_NAME_WEIGHT,
    "section_text": 0.0,   # body text gets weight from keyword groups only
    "raw_text": 0.0,        # same
}

# Source fields where we use the base weight directly (exact or fuzzy title match).
_STRUCTURED_TITLE_SOURCES = {"document_title", "section_title", "table_title"}


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------


def _normalised(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for comparison."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pattern_in_text(pattern: str, text: str) -> bool:
    """
    Case-insensitive substring match of *pattern* inside *text*.

    Both sides are normalised before comparison so that minor punctuation
    and whitespace differences (e.g. "M-MODE" vs "M MODE") do not cause
    false negatives.
    """
    return _normalised(pattern) in _normalised(text)


# ---------------------------------------------------------------------------
# Per-signature scoring
# ---------------------------------------------------------------------------


def _score_signature(
    signature: ReportSignature,
    signals: list[SignalCandidate],
) -> tuple[float, list[Evidence]]:
    """
    Score one signature against all signals.

    Returns
    -------
    raw_score : float
        Sum of matched weights (before exclusion penalty).
    evidence  : list[Evidence]
        Ordered list of evidence items (highest-weight first).

    Deduplication
    -------------
    Each (pattern, source_field) pair is counted at most once to prevent
    the same measurement appearing in both section_text and measurement_name
    from being double-counted.  We track matched patterns per source_field_group:
      - structured title sources share a dedup namespace
      - section_text / raw_text share a separate dedup namespace
    """
    evidence: list[Evidence] = []
    # Tracks (normalised_pattern, source_group) tuples already matched.
    matched_pairs: set[tuple[str, str]] = set()

    def _source_group(source_field: str) -> str:
        """Collapse source fields into dedup groups."""
        if source_field in _STRUCTURED_TITLE_SOURCES | {"table_header", "measurement_name"}:
            return source_field
        # section_text and raw_text share one namespace
        return "text"

    # --- Title-level patterns ---
    for signal in signals:
        if signal.source_field not in _STRUCTURED_TITLE_SOURCES:
            continue
        base_weight = _SOURCE_BASE_WEIGHTS[signal.source_field]
        for pattern in signature.title_patterns:
            key = (_normalised(pattern), signal.source_field)
            if key in matched_pairs:
                continue
            if _pattern_in_text(pattern, signal.text):
                matched_pairs.add(key)
                evidence.append(Evidence(
                    signal_text=signal.text,
                    signal_category="title_match",
                    source_field=signal.source_field,
                    weight=base_weight,
                    page=signal.page,
                    section=signal.section_context,
                    matched_pattern=pattern,
                ))

    # --- Section title patterns ---
    for signal in signals:
        if signal.source_field != "section_title":
            continue
        for pattern in signature.section_patterns:
            key = (_normalised(pattern), "section_title")
            if key in matched_pairs:
                continue
            if _pattern_in_text(pattern, signal.text):
                matched_pairs.add(key)
                evidence.append(Evidence(
                    signal_text=signal.text,
                    signal_category="section_indicator",
                    source_field="section_title",
                    weight=SECTION_TITLE_WEIGHT,
                    page=signal.page,
                    section=signal.section_context,
                    matched_pattern=pattern,
                ))

    # --- Table title / header patterns ---
    for signal in signals:
        if signal.source_field not in {"table_title", "table_header"}:
            continue
        base_weight = _SOURCE_BASE_WEIGHTS[signal.source_field]
        for pattern in signature.table_patterns:
            key = (_normalised(pattern), signal.source_field)
            if key in matched_pairs:
                continue
            if _pattern_in_text(pattern, signal.text):
                matched_pairs.add(key)
                evidence.append(Evidence(
                    signal_text=signal.text,
                    signal_category="table_indicator",
                    source_field=signal.source_field,
                    weight=base_weight,
                    page=signal.page,
                    section=signal.section_context,
                    matched_pattern=pattern,
                ))

    # --- Measurement name patterns ---
    for signal in signals:
        if signal.source_field != "measurement_name":
            continue
        for pattern in signature.measurement_patterns:
            key = (_normalised(pattern), "measurement_name")
            if key in matched_pairs:
                continue
            if _pattern_in_text(pattern, signal.text):
                matched_pairs.add(key)
                evidence.append(Evidence(
                    signal_text=signal.text,
                    signal_category="measurement_indicator",
                    source_field="measurement_name",
                    weight=MEASUREMENT_NAME_WEIGHT,
                    page=signal.page,
                    section=signal.section_context,
                    matched_pattern=pattern,
                ))

    # --- Keyword groups (strong + supporting) ---
    # Searched in section_text, section_title, table_title, and raw_text.
    keyword_sources = {
        "section_text", "raw_text",
        "section_title", "table_title", "document_title",
        "measurement_name",
    }
    all_kw_groups: list[SignalGroup] = (
        signature.strong_keyword_groups + signature.supporting_keyword_groups
    )
    for group in all_kw_groups:
        for pattern in group.patterns:
            for signal in signals:
                if signal.source_field not in keyword_sources:
                    continue
                sg = _source_group(signal.source_field)
                key = (_normalised(pattern), sg)
                if key in matched_pairs:
                    continue
                if _pattern_in_text(pattern, signal.text):
                    matched_pairs.add(key)
                    evidence.append(Evidence(
                        signal_text=signal.text[:120],  # truncate long body text
                        signal_category=group.category,
                        source_field=signal.source_field,
                        weight=group.weight,
                        page=signal.page,
                        section=signal.section_context,
                        matched_pattern=pattern,
                    ))

    # --- Compute raw score ---
    raw_score = sum(e.weight for e in evidence)

    # --- Exclusion check ---
    # Search exclusion patterns across ALL text signals.
    exclusion_hit = False
    all_text = " ".join(s.text for s in signals).lower()
    for excl in signature.exclusion_patterns:
        if _normalised(excl) in _normalised(all_text):
            exclusion_hit = True
            break

    if exclusion_hit and raw_score > 0:
        raw_score *= (1.0 - EXCLUSION_PENALTY)

    # Sort evidence by descending weight for readability.
    evidence.sort(key=lambda e: e.weight, reverse=True)

    return raw_score, evidence


# ---------------------------------------------------------------------------
# Score normalisation
# ---------------------------------------------------------------------------


def _normalise_score(raw_score: float) -> float:
    """
    Map raw score → confidence in [0.0, 1.0].

    Uses a simple linear clamp against NORMALISATION_CEILING.
    High-weight matches (e.g. direct title + several strong keywords)
    naturally produce high confidence without artificial inflation.
    """
    if raw_score <= 0:
        return 0.0
    return min(raw_score / NORMALISATION_CEILING, 1.0)


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


def _decide(
    scores: list[tuple[str, float, list[Evidence]]],
) -> ClassificationResult:
    """
    Given a list of (report_type, raw_score, evidence) tuples (sorted
    descending by score), produce the final ClassificationResult.

    The decision process:
    1. Filter to candidates that cleared MIN_VIABLE_SCORE.
    2. If none remain → UNKNOWN.
    3. If top candidate is sufficiently separated from second → CONFIDENT.
    4. If two or more are close → AMBIGUOUS.
    5. Otherwise → UNCERTAIN.
    """
    viable = [(rt, sc, ev) for rt, sc, ev in scores if sc >= MIN_VIABLE_SCORE]

    if not viable:
        top_score = scores[0][1] if scores else 0.0
        confidence = _normalise_score(top_score)
        alternatives = [
            Alternative(report_type=rt, score=round(sc, 4), evidence_count=len(ev))
            for rt, sc, ev in scores[:3]
            if sc > 0
        ]
        return ClassificationResult(
            report_type="unknown",
            confidence=confidence,
            status="UNKNOWN",
            evidence=[],
            alternatives=alternatives,
        )

    top_type, top_score, top_evidence = viable[0]
    confidence = _normalise_score(top_score)

    # Build alternatives list (all other viable candidates).
    alternatives = [
        Alternative(report_type=rt, score=round(sc, 4), evidence_count=len(ev))
        for rt, sc, ev in viable[1:]
    ]

    # Ambiguity check.
    if len(viable) >= 2:
        second_score = viable[1][1]
        gap = (top_score - second_score) / top_score if top_score > 0 else 1.0
        is_ambiguous = (
            gap < AMBIGUITY_GAP_FRACTION
            or top_score < second_score * AMBIGUITY_SEPARATION_FACTOR
        )
        if is_ambiguous:
            all_alts = [
                Alternative(report_type=rt, score=round(sc, 4), evidence_count=len(ev))
                for rt, sc, ev in viable
            ]
            return ClassificationResult(
                report_type="unknown",
                confidence=confidence,
                status="AMBIGUOUS",
                evidence=top_evidence,
                alternatives=all_alts,
            )

    # Confidence check.
    if top_score >= CONFIDENCE_THRESHOLD:
        status = "CONFIDENT"
    else:
        status = "UNCERTAIN"

    return ClassificationResult(
        report_type=top_type,
        confidence=confidence,
        status=status,
        evidence=top_evidence,
        alternatives=alternatives,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def classify(
    result: ExtractionResult,
    signatures: list[ReportSignature] | None = None,
) -> ClassificationResult:
    """
    Classify the report type of an extracted medical document.

    Parameters
    ----------
    result:
        The ExtractionResult produced by Phase 1.  Not modified.
    signatures:
        Optional list of ReportSignature objects to use.  Defaults to
        ALL_SIGNATURES from the signatures module.  Pass a custom list
        for testing or to restrict the candidate set.

    Returns
    -------
    ClassificationResult
        The classification with full evidence trail.
    """
    if signatures is None:
        signatures = ALL_SIGNATURES

    # Extract signals from the structured ExtractionResult.
    signals = extract_signals(result)

    logger.info(
        "classify: %d signals extracted from document '%s'",
        len(signals),
        result.document.file_name,
    )

    # Score each signature.
    scored: list[tuple[str, float, list[Evidence]]] = []
    for sig in signatures:
        raw_score, evidence = _score_signature(sig, signals)
        scored.append((sig.canonical_name, raw_score, evidence))
        logger.debug(
            "  %s: raw_score=%.2f, evidence_count=%d",
            sig.canonical_name,
            raw_score,
            len(evidence),
        )

    # Sort by score descending.
    scored.sort(key=lambda x: x[1], reverse=True)

    # Decide.
    classification = _decide(scored)

    logger.info(
        "classify result: type=%s, status=%s, confidence=%.3f",
        classification.report_type,
        classification.status,
        classification.confidence,
    )

    return classification
