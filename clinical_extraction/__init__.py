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
]
