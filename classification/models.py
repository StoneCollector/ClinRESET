"""
classification/models.py

Data models for the classification layer.

These are the stable, serialisable structures that form the contract
between the classification layer and all downstream phases.

Design rules
------------
- Every classification carries its evidence.
- Evidence is traceable to page, section, and matched text.
- Missing optional fields are None, never fabricated.
- No clinical interpretation is stored here — identification only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Evidence item
# ---------------------------------------------------------------------------


@dataclass
class Evidence:
    """
    A single piece of evidence that contributed to the classification score.

    Attributes
    ----------
    signal_text:
        The exact text that was matched (preserved from the document).
    signal_category:
        The type of signal: "title_match", "section_title", "table_title",
        "measurement_name", "strong_keyword", "supporting_keyword",
        "structural".
    source_field:
        Where in the document the signal was found: "document_title",
        "section_title", "table_title", "measurement_name", "raw_text".
    weight:
        The numerical weight assigned to this evidence item.
    page:
        Document page number (1-indexed), if known.
    section:
        Section title context, if applicable.
    matched_pattern:
        The pattern/keyword from the signature that produced this match.
    """

    signal_text: str
    signal_category: str
    source_field: str
    weight: float
    page: Optional[int] = None
    section: Optional[str] = None
    matched_pattern: Optional[str] = None


# ---------------------------------------------------------------------------
# Alternative candidate
# ---------------------------------------------------------------------------


@dataclass
class Alternative:
    """A runner-up report type with its raw score."""

    report_type: str
    score: float
    evidence_count: int


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """
    The output of the classification step.

    Statuses
    --------
    CONFIDENT   — a single report type scored above the confidence threshold
                  and sufficiently above all alternatives.
    UNCERTAIN   — the top score is above the minimum floor but below the
                  confidence threshold.
    AMBIGUOUS   — two or more report types scored too closely to separate.
    UNKNOWN     — no report type reached even the minimum floor score.
    """

    report_type: str                          # canonical name or "unknown"
    confidence: float                         # 0.0 – 1.0
    status: str                               # CONFIDENT | UNCERTAIN | AMBIGUOUS | UNKNOWN
    evidence: list[Evidence] = field(default_factory=list)
    alternatives: list[Alternative] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation suitable for JSON serialisation."""
        return {
            "report_type": self.report_type,
            "confidence": round(self.confidence, 4),
            "status": self.status,
            "evidence": [
                {
                    "signal_text": e.signal_text,
                    "signal_category": e.signal_category,
                    "source_field": e.source_field,
                    "weight": e.weight,
                    "page": e.page,
                    "section": e.section,
                    "matched_pattern": e.matched_pattern,
                }
                for e in self.evidence
            ],
            "alternatives": [
                {
                    "report_type": a.report_type,
                    "score": round(a.score, 4),
                    "evidence_count": a.evidence_count,
                }
                for a in self.alternatives
            ],
        }
