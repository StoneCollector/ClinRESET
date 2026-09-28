"""
Unified Clinical Explanation Engine for ClinRESET.
Provides fact-grounded patient explanations, strict numerical cross-checking,
and deterministic template fallbacks.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .llm_explainer import GroundedLLMExplainer
from .models import ConceptExplanation, ExplanationSection, ReportExplanation, VerificationResult
from .templates import DeterministicTemplateExplainer
from .verifier import NumericalCrossChecker

logger = logging.getLogger(__name__)


class ClinicalExplainer:
    """Orchestrates patient report explanations and zero-discrepancy numerical checks."""

    @classmethod
    def explain_report(
        cls,
        findings: List[Dict[str, Any]],
        report_type: Optional[str] = None,
        use_llm: bool = False,
        backend_name: Optional[str] = None,
        model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
    ) -> ReportExplanation:
        """
        Generates a verified, patient-friendly explanation for a clinical report.

        Args:
            findings: Normalized clinical findings and measurements.
            report_type: Imaging modality (e.g. 'echo', 'ct scans', 'mri').
            use_llm: If True and backend available, attempts LLM synthesis guarded by cross-checker.
            backend_name: 'ollama', 'hf_api', 'transformers', or None.
            model_name: Model identifier.
        """
        if use_llm:
            explainer = GroundedLLMExplainer(backend_name=backend_name, model_name=model_name)
            return explainer.explain(findings=findings, report_type=report_type)

        return DeterministicTemplateExplainer.explain_report(
            findings=findings,
            report_type=report_type,
        )

    @classmethod
    def verify_numbers(
        cls,
        generated_text: str,
        source_facts: List[Dict[str, Any]],
    ) -> VerificationResult:
        """Cross-checks numbers in text against source facts."""
        return NumericalCrossChecker.verify(generated_text, source_facts)
