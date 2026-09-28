"""
Data models for ClinRESET Terminology Normalization and Concept Standardization.
Maintains canonical terms, SNOMED/RadLex identifiers, layman explanations,
organ systems, and strict unknown term isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class AmbiguityStatus:
    """Explicit ambiguity statuses for clinical terminology resolution."""
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class CandidateConcept:
    """A candidate meaning/expansion for an abbreviation or term."""
    term: str
    domain: str = "general"
    source: str = "ClinRESET_corpus"
    is_safety_warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "domain": self.domain,
            "source": self.source,
            "is_safety_warning": self.is_safety_warning,
        }


@dataclass
class NormalizedConcept:
    """
    Standardized clinical concept record.

    Attributes:
        raw_term: Original text span from report (e.g. 'cardiomegaly', 'MPD')
        preferred_term: Standard medical term (e.g. 'Cardiomegaly', 'Main pancreatic duct')
        snomed_id: SNOMED CT Concept ID (e.g. 'SNOMED:8186001') if matched
        radlex_id: RadLex ID (e.g. 'RID50043') if matched
        layman_synonym: Patient-friendly explanation or plain English term
        organ_system: High-level anatomical category (Cardiovascular, Respiratory, etc.)
        is_known: True if recognized in medical ontology or corpus; False if noise/unmapped
        source: Provenance of resolution (e.g. 'corpus', 'cache', 'ols_snomed', 'unmapped')
        confidence: Confidence score (0.0 to 1.0)
    """
    raw_term: str
    preferred_term: str
    snomed_id: Optional[str] = None
    radlex_id: Optional[str] = None
    layman_synonym: Optional[str] = None
    organ_system: str = "General"
    is_known: bool = True
    source: str = "unmapped"
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_term": self.raw_term,
            "preferred_term": self.preferred_term,
            "snomed_id": self.snomed_id,
            "radlex_id": self.radlex_id,
            "layman_synonym": self.layman_synonym,
            "organ_system": self.organ_system,
            "is_known": self.is_known,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class ResolutionContext:
    """Contextual metadata passed to disambiguate domain-specific terms."""
    report_type: Optional[str] = None       # e.g. 'echo', 'ct scans', 'ultrasound'
    section_title: Optional[str] = None     # e.g. 'IMPRESSION', 'FINDINGS'
    nearby_text: Optional[str] = None
    anatomy_context: List[str] = field(default_factory=list)
