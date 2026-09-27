"""
clinical_extraction/terminology/models.py

Data structures for the terminology normalization and abbreviation disambiguation subsystem.

Preserves surface forms, canonical normalized terms, domain contexts, candidate meanings,
ambiguity statuses, safety alerts, and provenance without clinical interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class AmbiguityStatus:
    """Explicit ambiguity statuses for clinical terminology resolution."""

    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"

    ALL = {RESOLVED, AMBIGUOUS, UNKNOWN, NOT_APPLICABLE}


@dataclass
class CandidateConcept:
    """
    A single candidate meaning/expansion for an abbreviation.

    Attributes
    ----------
    term:
        Expanded canonical term (e.g. "Right Atrium", "Mitral Stenosis").
    domain:
        Clinical specialty or context (e.g. "echocardiography", "cardiovascular", "neurology").
    source:
        Corpus file line or source collection (e.g. "ASE", "MedlinePlus", "Joint Commission").
    is_safety_warning:
        True if this term is an error-prone abbreviation flagged on the Joint Commission safety list.
    """

    term: str
    domain: str = "general"
    source: str = "ClinRESET_medical_abbreviation_terminology_corpus.txt"
    is_safety_warning: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "domain": self.domain,
            "source": self.source,
            "is_safety_warning": self.is_safety_warning,
        }


@dataclass
class TerminologyRecord:
    """
    A structured record representing an abbreviation in the reference corpus.

    Attributes
    ----------
    surface_form:
        Original abbreviation string (e.g. "RA", "LVH", "MS").
    normalized_term:
        Unambiguous canonical term if singular, or resolved term; None if unresolved/ambiguous.
    domain:
        Primary domain or context description.
    candidates:
        List of all known candidate meanings.
    ambiguity:
        True if the surface form possesses multiple competing meanings across or within domains.
    ambiguity_status:
        One of AmbiguityStatus: RESOLVED, AMBIGUOUS, UNKNOWN, NOT_APPLICABLE.
    source:
        Origin source name / line numbers.
    confidence:
        Confidence descriptor (e.g. "source-backed").
    """

    surface_form: str
    normalized_term: Optional[str] = None
    domain: str = "general"
    candidates: list[CandidateConcept] = field(default_factory=list)
    ambiguity: bool = False
    ambiguity_status: str = AmbiguityStatus.RESOLVED
    source: str = "ClinRESET_medical_abbreviation_terminology_corpus.txt"
    confidence: str = "source-backed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_form": self.surface_form,
            "normalized_term": self.normalized_term,
            "domain": self.domain,
            "candidates": [c.to_dict() for c in self.candidates],
            "ambiguity": self.ambiguity,
            "ambiguity_status": self.ambiguity_status,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class ResolutionContext:
    """
    Contextual signals passed into the disambiguation engine,
    in strictly descending order of resolution priority.
    """

    report_type: Optional[str] = None
    section_title: Optional[str] = None
    nearby_text: Optional[str] = None
    anatomy_context: list[str] = field(default_factory=list)
    measurement_context: list[str] = field(default_factory=list)
    extracted_entities: list[Any] = field(default_factory=list)
    relationships: list[Any] = field(default_factory=list)
    domain_mappings: Optional[dict[str, str]] = None


@dataclass
class ResolutionResult:
    """
    The final output of normalizing a clinical surface form.

    Attributes
    ----------
    text:
        Exact original surface form encountered.
    normalized:
        Standardised medical term if resolved, else None.
    normalization_source:
        Provenance source string (e.g. "terminology_corpus", "report_specific_rules").
    ambiguity:
        True if the surface form remains ambiguous without decisive context.
    ambiguity_status:
        RESOLVED | AMBIGUOUS | UNKNOWN | NOT_APPLICABLE.
    candidates:
        List of candidate meanings when ambiguous or alternative expansions.
    domain:
        Matched domain context, if known.
    safety_warning:
        Optional safety note if abbreviation is on the Joint Commission 'Do Not Use' list.
    provenance:
        Detailed traceability string showing which signal resolved the abbreviation.
    """

    text: str
    normalized: Optional[str] = None
    normalization_source: Optional[str] = None
    ambiguity: bool = False
    ambiguity_status: str = AmbiguityStatus.UNKNOWN
    candidates: list[str] = field(default_factory=list)
    domain: Optional[str] = None
    safety_warning: Optional[str] = None
    provenance: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Plain dictionary suitable for JSON serialization in report.json."""
        d: dict[str, Any] = {
            "text": self.text,
            "normalized": self.normalized,
            "normalization_source": self.normalization_source,
            "ambiguity": self.ambiguity,
            "ambiguity_status": self.ambiguity_status,
        }
        if self.candidates:
            d["candidates"] = self.candidates
        if self.domain:
            d["domain"] = self.domain
        if self.safety_warning:
            d["safety_warning"] = self.safety_warning
        if self.provenance:
            d["provenance"] = self.provenance
        return d
