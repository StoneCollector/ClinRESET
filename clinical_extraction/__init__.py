"""
clinical_extraction/__init__.py

Phase 3: Clinical Information Extraction layer.

Transforms classified reports into structured clinical information:
- Reuses and enriches measurements
- Extracts findings with explicit negation and assertion tracking
- Extracts anatomical entities
- Normalizes terminology while preserving exact source text
- Establishes traceable relationships without clinical interpretation
"""

from clinical_extraction.extractor import extract_clinical_info
from clinical_extraction.models import (
    AnatomicalEntity,
    AssertionStatus,
    ClinicalEntity,
    ClinicalFinding,
    ClinicalInformation,
    ClinicalMeasurement,
    ClinicalRelationship,
    EntityType,
    RelationType,
    SemanticCategory,
)
from clinical_extraction.normalization import normalize_term, resolve_term
from clinical_extraction.semantic import assign_semantic_metadata
from clinical_extraction.terminology import (
    AmbiguityStatus,
    CandidateConcept,
    ResolutionContext,
    ResolutionResult,
    TerminologyCorpus,
    TerminologyRecord,
    TerminologyResolver,
    get_corpus,
    get_resolver,
)

__all__ = [
    "extract_clinical_info",
    "ClinicalInformation",
    "ClinicalEntity",
    "ClinicalFinding",
    "ClinicalMeasurement",
    "AnatomicalEntity",
    "ClinicalRelationship",
    "EntityType",
    "AssertionStatus",
    "RelationType",
    "SemanticCategory",
    "assign_semantic_metadata",
    "normalize_term",
    "resolve_term",
    "AmbiguityStatus",
    "CandidateConcept",
    "TerminologyRecord",
    "ResolutionContext",
    "ResolutionResult",
    "TerminologyCorpus",
    "TerminologyResolver",
    "get_corpus",
    "get_resolver",
]
