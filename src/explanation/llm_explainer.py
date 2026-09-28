"""
Grounded LLM Explainer with Strict Numerical Verification for ClinRESET.
Uses small language models or APIs to synthesize compassionate patient summaries,
guarded by NumericalCrossChecker to reject any numerical discrepancies.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.extraction.model.model_plugins import ModelSelector
from .models import ReportExplanation, VerificationResult
from .templates import DeterministicTemplateExplainer
from .verifier import NumericalCrossChecker

logger = logging.getLogger(__name__)

EXPLANATION_PROMPT_TEMPLATE = """You are a compassionate medical communicator helping a patient understand their medical imaging report.
Explain the following verified clinical findings in plain, clear, reassuring English at a 6th-grade reading level.

STRICT SAFETY INSTRUCTIONS:
1. Every measurement, number, and reference range you mention MUST match the provided facts EXACTLY.
2. DO NOT invent, guess, calculate, or alter any numbers.
3. DO NOT introduce new medical diagnoses not mentioned below.
4. Keep the explanation under 150 words.

VERIFIED REPORT FACTS:
{facts_blob}

PATIENT SUMMARY:"""


class GroundedLLMExplainer:
    """Generates patient-accessible report summaries using LLMs with strict numerical verification."""

    def __init__(
        self,
        backend_name: Optional[str] = None,
        model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
    ):
        self.backend_name = backend_name
        self.model_name = model_name

    def explain(
        self,
        findings: List[Dict[str, Any]],
        report_type: Optional[str] = None,
    ) -> ReportExplanation:
        """
        Attempts to generate an explanation via LLM; verifies all numbers;
        falls back to deterministic template if offline or if numerical discrepancy is found.
        """
        template_result = DeterministicTemplateExplainer.explain_report(
            findings=findings,
            report_type=report_type,
        )

        backend = ModelSelector.get_backend(self.backend_name, model_name=self.model_name)
        if not backend or backend.name == "heuristic" or not backend.is_available():
            logger.info("LLM backend not available or offline. Using deterministic template explanation.")
            return template_result

        # Build verified facts blob
        fact_lines = []
        for f in findings:
            c = f.get("preferred_term") or f.get("concept") or "Finding"
            assertion = f.get("assertion", "PRESENT")
            val = f.get("value")
            unit = f.get("unit") or ""
            ref = f.get("reference_range")
            layman = f.get("layman_synonym")

            line = f"- {c}"
            if layman:
                line += f" ({layman})"
            line += f": {assertion}"
            if val is not None:
                line += f", measured at {val} {unit}".strip()
            if ref:
                line += f" (standard reference: {ref})"
            fact_lines.append(line)

        facts_blob = "\n".join(fact_lines)
        prompt = EXPLANATION_PROMPT_TEMPLATE.format(facts_blob=facts_blob)

        try:
            # Query backend
            llm_text = ""
            if hasattr(backend, "extract_raw_text"):
                llm_text = backend.extract_raw_text(prompt)
            else:
                # Backend fallback
                return template_result

            if not llm_text or len(llm_text.strip()) < 20:
                return template_result

            # Strict numerical verification
            verification = NumericalCrossChecker.verify(llm_text, findings)

            if not verification.is_valid:
                logger.warning(
                    f"LLM generated ungrounded numbers: {verification.discrepancies}. "
                    "Rejecting LLM output and falling back to verified deterministic template."
                )
                template_result.verification = verification
                return template_result

            # Validated LLM output!
            template_result.patient_summary = llm_text.strip()
            template_result.generation_mode = "grounded_llm"
            template_result.verification = verification
            return template_result

        except Exception as e:
            logger.warning(f"LLM explanation generation encountered error: {e}. Falling back to template.")
            return template_result
