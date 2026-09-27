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

    ALL = {
        ASSOCIATED_WITH,
        LOCATED_IN,
        MEASURES,
        HAS_MEASUREMENT,
        EVALUATES,
        HAS_FINDING,
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
    assertion: str = AssertionStatus.PRESENT
    negated: bool = False
    page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        return {
            "text": self.text,
            "type": self.type,
            "normalized": self.normalized,
            "assertion": self.assertion,
            "negated": self.negated,
            "page": self.page,
            "source_section": self.source_section,
            "source_text": self.source_text,
            "confidence": round(self.confidence, 4),
        }


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
    """

    name: str
    value: Any
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    normalized_name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "reference_range": self.reference_range,
            "page": self.page,
            "source_section": self.source_section,
            "source_text": self.source_text,
            "normalized_name": self.normalized_name,
        }


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
    assertion: str = AssertionStatus.PRESENT
    negated: bool = False
    page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        return {
            "text": self.text,
            "normalized": self.normalized,
            "assertion": self.assertion,
            "negated": self.negated,
            "page": self.page,
            "source_section": self.source_section,
            "source_text": self.source_text,
        }


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
    page:
        1-indexed document page number.
    source_section:
        Section title containing the anatomical mention.
    source_text:
        Verbatim context containing the anatomical mention.
    """

    text: str
    normalized: Optional[str] = None
    page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation."""
        return {
            "text": self.text,
            "normalized": self.normalized,
            "page": self.page,
            "source_section": self.source_section,
            "source_text": self.source_text,
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for JSON serialisation in report.json."""
        return {
            "entities": [e.to_dict() for e in self.entities],
            "measurements": [m.to_dict() for m in self.measurements],
            "findings": [f.to_dict() for f in self.findings],
            "anatomy": [a.to_dict() for a in self.anatomy],
            "relationships": [r.to_dict() for r in self.relationships],
        }
