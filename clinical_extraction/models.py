"""
clinical_extraction/models.py

Data models for the clinical information extraction layer (Phase 3).

These data models represent the structured clinical facts extracted from
the document without clinical interpretation, disease inference, or diagnostic
extrapolations.

Design rules
------------
- Strictly extraction, NOT clinical interpretation.
- Preserve original wording; normalization is stored in a separate field.
- Every clinical fact preserves source provenance (source text, page, section).
- Missing optional fields are None, never fabricated.
- Serialisable to plain Python dicts matching canonical report.json format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from clinical_extraction.terminology.models import AmbiguityStatus


# ---------------------------------------------------------------------------
# Enumerations and constants
# ---------------------------------------------------------------------------


class EntityType:
    """Configurable clinical entity categories."""

    ANATOMY = "ANATOMY"
    CONDITION = "CONDITION"
    DIAGNOSIS = "DIAGNOSIS"
    SYMPTOM = "SYMPTOM"
    FINDING = "FINDING"
    OBSERVATION = "OBSERVATION"
    MEASUREMENT = "MEASUREMENT"
    PROCEDURE = "PROCEDURE"
    MEDICATION = "MEDICATION"
    TREATMENT = "TREATMENT"
    TEST = "TEST"
    LAB_PARAMETER = "LAB_PARAMETER"
    TEMPORAL = "TEMPORAL"
    OTHER_CLINICAL = "OTHER_CLINICAL"

    ALL = {
        ANATOMY,
        CONDITION,
        DIAGNOSIS,
        SYMPTOM,
        FINDING,
        OBSERVATION,
        MEASUREMENT,
        PROCEDURE,
        MEDICATION,
        TREATMENT,
        TEST,
        LAB_PARAMETER,
        TEMPORAL,
        OTHER_CLINICAL,
    }


class AssertionStatus:
    """Contextual assertion / status of a clinical entity or finding."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    NORMAL = "NORMAL"
    POSSIBLE = "POSSIBLE"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"

    ALL = {PRESENT, ABSENT, NORMAL, POSSIBLE, HISTORICAL, UNKNOWN}


class RelationType:
    """Clinical relationship types established directly by source text."""

    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    LOCATED_IN = "LOCATED_IN"
    MEASURES = "MEASURES"
    HAS_MEASUREMENT = "HAS_MEASUREMENT"
    EVALUATES = "EVALUATES"
    HAS_FINDING = "HAS_FINDING"
    RELATES_TO = "RELATES_TO"

    ALL = {
        ASSOCIATED_WITH,
        LOCATED_IN,
        MEASURES,
        HAS_MEASUREMENT,
        EVALUATES,
        HAS_FINDING,
        RELATES_TO,
    }


class SemanticCategory:
    """Standard controlled clinical semantic categories for Phase 4 / Phase 5."""

    ANATOMY = "ANATOMY"
    MEASUREMENT = "MEASUREMENT"
    FUNCTION = "FUNCTION"
    STRUCTURAL_FINDING = "STRUCTURAL_FINDING"
    WALL_MOTION = "WALL_MOTION"
    DIASTOLIC_FUNCTION = "DIASTOLIC_FUNCTION"
    VALVULAR_FINDING = "VALVULAR_FINDING"
    PRESSURE = "PRESSURE"
    DOPPLER_MEASUREMENT = "DOPPLER_MEASUREMENT"
    THROMBUS = "THROMBUS"
    EFFUSION = "EFFUSION"
    PROCEDURE = "PROCEDURE"
    OTHER_CLINICAL = "OTHER_CLINICAL"

    ALL = {
        ANATOMY,
        MEASUREMENT,
        FUNCTION,
        STRUCTURAL_FINDING,
        WALL_MOTION,
        DIASTOLIC_FUNCTION,
        VALVULAR_FINDING,
        PRESSURE,
        DOPPLER_MEASUREMENT,
        THROMBUS,
        EFFUSION,
        PROCEDURE,
        OTHER_CLINICAL,
    }


# ---------------------------------------------------------------------------
# Individual Clinical Artifacts
# ---------------------------------------------------------------------------


@dataclass
class ClinicalEntity:
    """
    A single clinical entity extracted from the report.

    Attributes
    ----------
    text:
        Exact entity text as it appears in the source document.
    type:
        Entity category from EntityType (e.g. FINDING, ANATOMY, MEASUREMENT).
    normalized:
        Standardised terminology representation if known, else None.
    assertion:
        Contextual status: PRESENT, ABSENT, NORMAL, POSSIBLE, HISTORICAL, UNKNOWN.
    negated:
        True if the entity is explicitly negated (e.g. "No RWMA").
    page:
        1-indexed document page number where the entity appears.
    source_section:
        Section title in which the entity was found.
    source_text:
        Verbatim phrase or sentence containing the entity for traceability.
    confidence:
        Confidence score of the extraction (1.0 for deterministic rules).
    """

    text: str
    type: str
    normalized: Optional[str] = None
    normalization_source: Optional[str] = None
    ambiguity: bool = False
    ambiguity_status: str = AmbiguityStatus.RESOLVED
    candidates: list[str] = field(default_factory=list)
    assertion: str = AssertionStatus.PRESENT
    negated: bool = False
    page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    confidence: float = 1.0
    semantic_category: Optional[str] = None
    modifiers: dict[str, Any] = field(default_factory=dict)
    related_anatomy: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        d: dict[str, Any] = {
            "text": self.text,
            "type": self.type,
            "normalized": self.normalized,
            "normalization_source": self.normalization_source,
            "ambiguity": self.ambiguity,
            "ambiguity_status": self.ambiguity_status,
            "assertion": self.assertion,
            "negated": self.negated,
            "page": self.page,
            "source_section": self.source_section,
            "source_text": self.source_text,
            "confidence": round(self.confidence, 4),
            "semantic_category": self.semantic_category,
            "modifiers": self.modifiers,
            "related_anatomy": self.related_anatomy,
        }
        if self.candidates:
            d["candidates"] = self.candidates
        return d


@dataclass
class ClinicalMeasurement:
    """
    A quantitative or qualitative measurement value.

    Reuses normalized measurements from Phase 1 and adds inline measurements
    found in clinical narratives.

    Attributes
    ----------
    name:
        Measurement parameter name (e.g. 'Ejection Fraction', 'PASP').
    value:
        Measurement value (numeric or qualitative string).
    unit:
        Measurement unit (e.g. '%', 'mmHg', 'mm') if explicitly present.
        Never fabricated.
    reference_range:
        Reported reference range (e.g. '55-74%') if explicitly present.
    page:
        1-indexed document page number.
    source_section:
        Section title containing the measurement.
    source_text:
        Verbatim source text snippet for traceability.
    normalized_name:
        Standardised parameter name if mapped, else None.
    normalization_source:
        Provenance source string.
    ambiguity:
        True if the parameter name has unresolved competing expansions.
    ambiguity_status:
        RESOLVED | AMBIGUOUS | UNKNOWN | NOT_APPLICABLE.
    candidates:
        Alternative expansions if ambiguous.
    """

    name: str
    value: Any
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    normalized_name: Optional[str] = None
    normalization_source: Optional[str] = None
    ambiguity: bool = False
    ambiguity_status: str = AmbiguityStatus.RESOLVED
    candidates: list[str] = field(default_factory=list)
    semantic_category: Optional[str] = None
    modifiers: dict[str, Any] = field(default_factory=dict)
    related_anatomy: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        d: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "reference_range": self.reference_range,
            "page": self.page,
            "source_section": self.source_section,
            "source_text": self.source_text,
            "normalized_name": self.normalized_name,
            "normalization_source": self.normalization_source,
            "ambiguity": self.ambiguity,
            "ambiguity_status": self.ambiguity_status,
            "semantic_category": self.semantic_category,
            "modifiers": self.modifiers,
            "related_anatomy": self.related_anatomy,
        }
        if self.candidates:
            d["candidates"] = self.candidates
        return d


@dataclass
class ClinicalFinding:
    """
    An explicit clinical observation or finding.

    Preserves original wording and records explicit negation and assertion.

    Attributes
    ----------
    text:
        Exact wording of the finding (e.g. "No RWMA", "Conc LVH", "Mild TR").
    normalized:
        Standardised medical term if a reliable mapping exists, else None.
    normalization_source:
        Provenance source string.
    ambiguity:
        True if the finding expression is ambiguous.
    ambiguity_status:
        RESOLVED | AMBIGUOUS | UNKNOWN | NOT_APPLICABLE.
    candidates:
        Alternative expansions if ambiguous.
    assertion:
        Assertion status: PRESENT, ABSENT, NORMAL, POSSIBLE, HISTORICAL, UNKNOWN.
    negated:
        True if the finding is negated in source text.
    page:
        1-indexed document page number.
    source_section:
        Section title containing the finding.
    source_text:
        Verbatim sentence or clause containing the finding.
    """

    text: str
    normalized: Optional[str] = None
    normalization_source: Optional[str] = None
    ambiguity: bool = False
    ambiguity_status: str = AmbiguityStatus.RESOLVED
    candidates: list[str] = field(default_factory=list)
    assertion: str = AssertionStatus.PRESENT
    negated: bool = False
    page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    semantic_category: Optional[str] = None
    modifiers: dict[str, Any] = field(default_factory=dict)
    related_anatomy: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        d: dict[str, Any] = {
            "text": self.text,
            "normalized": self.normalized,
            "normalization_source": self.normalization_source,
            "ambiguity": self.ambiguity,
            "ambiguity_status": self.ambiguity_status,
            "assertion": self.assertion,
            "negated": self.negated,
            "page": self.page,
            "source_section": self.source_section,
            "source_text": self.source_text,
            "semantic_category": self.semantic_category,
            "modifiers": self.modifiers,
            "related_anatomy": self.related_anatomy,
        }
        if self.candidates:
            d["candidates"] = self.candidates
        return d


@dataclass
class AnatomicalEntity:
    """
    An anatomical structure explicitly mentioned in the report.

    Attributes
    ----------
    text:
        Original anatomical term (e.g. "left ventricle", "mitral valve", "LV").
    normalized:
        Standardised anatomical term (e.g. "Left Ventricle", "Mitral Valve").
    normalization_source:
        Provenance source string.
    ambiguity:
        True if the anatomical mention is ambiguous.
    ambiguity_status:
        RESOLVED | AMBIGUOUS | UNKNOWN | NOT_APPLICABLE.
    candidates:
        Alternative expansions if ambiguous.
    page:
        1-indexed document page number.
    source_section:
        Section title containing the anatomical mention.
    source_text:
        Verbatim context containing the anatomical mention.
    """

    text: str
    normalized: Optional[str] = None
    normalization_source: Optional[str] = None
    ambiguity: bool = False
    ambiguity_status: str = AmbiguityStatus.RESOLVED
    candidates: list[str] = field(default_factory=list)
    page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    semantic_category: str = "ANATOMY"
    modifiers: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        d: dict[str, Any] = {
            "text": self.text,
            "normalized": self.normalized,
            "normalization_source": self.normalization_source,
            "ambiguity": self.ambiguity,
            "ambiguity_status": self.ambiguity_status,
            "page": self.page,
            "source_section": self.source_section,
            "source_text": self.source_text,
            "semantic_category": self.semantic_category,
            "modifiers": self.modifiers,
        }
        if self.candidates:
            d["candidates"] = self.candidates
        return d


@dataclass
class ClinicalRelationship:
    """
    A relationship connecting two extracted clinical items.

    Must be explicitly supported by source text syntax or structured data.
    Never speculative.

    Attributes
    ----------
    source:
        Source entity or finding term (e.g. "LVH", "Ejection Fraction").
    relation:
        Relationship type from RelationType (e.g. "ASSOCIATED_WITH", "MEASURES").
    target:
        Target entity (e.g. "left ventricle", "60%").
    page:
        1-indexed document page number.
    source_text:
        Sentence or clause establishing the relationship.
    """

    source: str
    relation: str
    target: str
    page: Optional[int] = None
    source_text: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        return {
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
            "page": self.page,
            "source_text": self.source_text,
        }


# ---------------------------------------------------------------------------
# Top-level Clinical Information Container
# ---------------------------------------------------------------------------


@dataclass
class ClinicalInformation:
    """
    Complete structured clinical information extracted from the report.

    Forms the "clinical_information" section in report.json.
    """

    entities: list[ClinicalEntity] = field(default_factory=list)
    measurements: list[ClinicalMeasurement] = field(default_factory=list)
    findings: list[ClinicalFinding] = field(default_factory=list)
    anatomy: list[AnatomicalEntity] = field(default_factory=list)
    relationships: list[ClinicalRelationship] = field(default_factory=list)
    explanations: list[dict[str, Any]] = field(default_factory=list)
    explanation_sections: list[dict[str, Any]] = field(default_factory=list)

    def to_phase5_contract(self) -> list[dict[str, Any]]:
        """
        Produce validated structured clinical concepts conforming to the Phase 5 contract:
        {
          "concept": "...",
          "original_text": "...",
          "type": "...",
          "semantic_category": "...",
          "value": null,
          "unit": null,
          "reference_range": null,
          "assertion": "...",
          "modifiers": {},
          "related_anatomy": [],
          "provenance": {}
        }
        """
        concepts: list[dict[str, Any]] = []

        for f in self.findings:
            concepts.append({
                "concept": f.normalized or f.text,
                "original_text": f.text,
                "type": EntityType.FINDING,
                "semantic_category": f.semantic_category or SemanticCategory.OTHER_CLINICAL,
                "value": None,
                "unit": None,
                "reference_range": None,
                "assertion": f.assertion,
                "modifiers": dict(f.modifiers),
                "related_anatomy": list(f.related_anatomy),
                "provenance": {
                    "page": f.page,
                    "source_section": f.source_section,
                    "source_text": f.source_text,
                    "normalization_source": f.normalization_source,
                    "ambiguity": f.ambiguity,
                    "ambiguity_status": f.ambiguity_status,
                    "candidates": list(f.candidates),
                },
            })

        for m in self.measurements:
            concepts.append({
                "concept": m.normalized_name or m.name,
                "original_text": m.name,
                "type": EntityType.MEASUREMENT,
                "semantic_category": m.semantic_category or SemanticCategory.MEASUREMENT,
                "value": m.value,
                "unit": m.unit,
                "reference_range": m.reference_range,
                "assertion": AssertionStatus.PRESENT,
                "modifiers": dict(m.modifiers),
                "related_anatomy": list(m.related_anatomy),
                "provenance": {
                    "page": m.page,
                    "source_section": m.source_section,
                    "source_text": m.source_text,
                    "normalization_source": m.normalization_source,
                    "ambiguity": m.ambiguity,
                    "ambiguity_status": m.ambiguity_status,
                    "candidates": list(m.candidates),
                },
            })

        return concepts

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation in report.json."""
        d: dict[str, Any] = {
            "entities": [e.to_dict() for e in self.entities],
            "measurements": [m.to_dict() for m in self.measurements],
            "findings": [f.to_dict() for f in self.findings],
            "anatomy": [a.to_dict() for a in self.anatomy],
            "relationships": [r.to_dict() for r in self.relationships],
            "structured_clinical_concepts": self.to_phase5_contract(),
        }
        if self.explanations:
            d["explanations"] = self.explanations
        if self.explanation_sections:
            d["explanation_sections"] = self.explanation_sections
        return d

