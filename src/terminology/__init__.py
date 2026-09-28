"""
ClinRESET Terminology Normalization Package.
Provides standardized medical concepts, SNOMED CT identifiers, layman explanations,
organ system categorization, and dynamic offline-first caching.
"""

from .models import (
    AmbiguityStatus,
    CandidateConcept,
    NormalizedConcept,
    ResolutionContext,
)
from .corpus import LocalCorpus
from .client import TerminologyClient
from .normalizer import TerminologyNormalizer

__all__ = [
    "AmbiguityStatus",
    "CandidateConcept",
    "NormalizedConcept",
    "ResolutionContext",
    "LocalCorpus",
    "TerminologyClient",
    "TerminologyNormalizer",
]
