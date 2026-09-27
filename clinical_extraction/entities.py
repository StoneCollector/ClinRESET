"""
clinical_extraction/entities.py

Clinical entity taxonomy and entity building utilities.

Provides helper methods for entity taxonomy management, validation,
and entity instantiations with full provenance tracking.
"""

from __future__ import annotations

from typing import Optional

from clinical_extraction.models import (
    AmbiguityStatus,
    AnatomicalEntity,
    AssertionStatus,
    ClinicalEntity,
    ClinicalFinding,
    ClinicalMeasurement,
    ClinicalRelationship,
    EntityType,
    RelationType,
)


def validate_entity_type(entity_type: str) -> bool:
    """Check if the entity type conforms to the clinical taxonomy."""
    return entity_type in EntityType.ALL


def validate_assertion_status(assertion: str) -> bool:
    """Check if the assertion status conforms to allowed statuses."""
    return assertion in AssertionStatus.ALL


def create_entity(
    text: str,
    entity_type: str,
    normalized: Optional[str] = None,
    assertion: str = AssertionStatus.PRESENT,
    negated: bool = False,
    page: Optional[int] = None,
    source_section: Optional[str] = None,
    source_text: Optional[str] = None,
    confidence: float = 1.0,
    normalization_source: Optional[str] = None,
    ambiguity: bool = False,
    ambiguity_status: str = AmbiguityStatus.RESOLVED,
    candidates: Optional[list[str]] = None,
) -> ClinicalEntity:
    """Create a validated ClinicalEntity with complete provenance."""
    if not validate_entity_type(entity_type):
        entity_type = EntityType.OTHER_CLINICAL

    if not validate_assertion_status(assertion):
        assertion = AssertionStatus.UNKNOWN

    return ClinicalEntity(
        text=text.strip(),
        type=entity_type,
        normalized=normalized,
        normalization_source=normalization_source,
        ambiguity=ambiguity,
        ambiguity_status=ambiguity_status,
        candidates=candidates or [],
        assertion=assertion,
        negated=negated,
        page=page,
        source_section=source_section,
        source_text=source_text.strip() if source_text else None,
        confidence=confidence,
    )


def create_finding(
    text: str,
    normalized: Optional[str] = None,
    assertion: str = AssertionStatus.PRESENT,
    negated: bool = False,
    page: Optional[int] = None,
    source_section: Optional[str] = None,
    source_text: Optional[str] = None,
    normalization_source: Optional[str] = None,
    ambiguity: bool = False,
    ambiguity_status: str = AmbiguityStatus.RESOLVED,
    candidates: Optional[list[str]] = None,
) -> ClinicalFinding:
    """Create a ClinicalFinding tracking negation and assertion."""
    if not validate_assertion_status(assertion):
        assertion = AssertionStatus.UNKNOWN

    return ClinicalFinding(
        text=text.strip(),
        normalized=normalized,
        normalization_source=normalization_source,
        ambiguity=ambiguity,
        ambiguity_status=ambiguity_status,
        candidates=candidates or [],
        assertion=assertion,
        negated=negated,
        page=page,
        source_section=source_section,
        source_text=source_text.strip() if source_text else None,
    )


def create_anatomy(
    text: str,
    normalized: Optional[str] = None,
    page: Optional[int] = None,
    source_section: Optional[str] = None,
    source_text: Optional[str] = None,
    normalization_source: Optional[str] = None,
    ambiguity: bool = False,
    ambiguity_status: str = AmbiguityStatus.RESOLVED,
    candidates: Optional[list[str]] = None,
) -> AnatomicalEntity:
    """Create an AnatomicalEntity tracking location and source."""
    return AnatomicalEntity(
        text=text.strip(),
        normalized=normalized,
        normalization_source=normalization_source,
        ambiguity=ambiguity,
        ambiguity_status=ambiguity_status,
        candidates=candidates or [],
        page=page,
        source_section=source_section,
        source_text=source_text.strip() if source_text else None,
    )


def create_relationship(
    source: str,
    relation: str,
    target: str,
    page: Optional[int] = None,
    source_text: Optional[str] = None,
) -> ClinicalRelationship:
    """Create a ClinicalRelationship between source and target."""
    if relation not in RelationType.ALL:
        relation = RelationType.ASSOCIATED_WITH

    return ClinicalRelationship(
        source=source.strip(),
        relation=relation,
        target=target.strip(),
        page=page,
        source_text=source_text.strip() if source_text else None,
    )
