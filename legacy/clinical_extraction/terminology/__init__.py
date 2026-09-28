"""
clinical_extraction/terminology/__init__.py

Terminology normalization and abbreviation disambiguation package.
"""

from clinical_extraction.terminology.corpus_loader import (
    DEFAULT_CORPUS_PATH,
    SAFETY_ABBREVIATIONS,
    TerminologyCorpus,
    get_corpus,
)
from clinical_extraction.terminology.models import (
    AmbiguityStatus,
    CandidateConcept,
    ResolutionContext,
    ResolutionResult,
    TerminologyRecord,
)
from clinical_extraction.terminology.resolver import (
    TerminologyResolver,
    get_resolver,
)

__all__ = [
    "AmbiguityStatus",
    "CandidateConcept",
    "TerminologyRecord",
    "ResolutionContext",
    "ResolutionResult",
    "TerminologyCorpus",
    "get_corpus",
    "DEFAULT_CORPUS_PATH",
    "SAFETY_ABBREVIATIONS",
    "TerminologyResolver",
    "get_resolver",
]
