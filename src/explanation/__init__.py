"""
ClinRESET Clinical Explanation Package.
Generates patient-accessible report explanations with strict numerical cross-checking
and deterministic offline template fallbacks.
"""

from .models import (
    ConceptExplanation,
    ExplanationSection,
    ReportExplanation,
    VerificationResult,
)
from .verifier import NumericalCrossChecker
from .templates import DeterministicTemplateExplainer
from .llm_explainer import GroundedLLMExplainer
from .engine import ClinicalExplainer

__all__ = [
    "ConceptExplanation",
    "ExplanationSection",
    "ReportExplanation",
    "VerificationResult",
    "NumericalCrossChecker",
    "DeterministicTemplateExplainer",
    "GroundedLLMExplainer",
    "ClinicalExplainer",
]
