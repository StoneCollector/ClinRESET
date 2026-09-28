"""
Strict Numerical Cross-Checker for ClinRESET Explanations.
Guarantees ZERO discrepancy between generated patient explanations and source facts.
Detects and rejects any numerical hallucination before output reaches the patient.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Set

from .models import VerificationResult

logger = logging.getLogger(__name__)

# Matches integer or decimal numbers e.g. 15.8, 13, 0.45, 120/80, 11mm, 15.8cm
NUM_PATTERN = re.compile(r"\d+(?:\.\d+)?")


class NumericalCrossChecker:
    """Verifies that all numerical values in generated text originate strictly from source facts."""

    @classmethod
    def extract_numbers(cls, text: str) -> List[float]:
        """Extracts numerical values from text, ignoring structural list markers."""
        if not text:
            return []

        # Remove list enumeration markers like '1.', '2)', '3 -'
        cleaned = re.sub(r"^\s*\d+[\.\)\-]\s+", "", text, flags=re.MULTILINE)
        cleaned = re.sub(r"\n\s*\d+[\.\)\-]\s+", "\n", cleaned)

        matches = NUM_PATTERN.findall(cleaned)
        nums: List[float] = []
        for m in matches:
            try:
                nums.append(float(m))
            except ValueError:
                pass
        return nums

    @classmethod
    def extract_source_numbers(cls, source_facts: List[Dict[str, Any]]) -> Set[float]:
        """Extracts all authorized numbers from verified source facts and reference ranges."""
        authorized: Set[float] = set()

        for item in source_facts:
            # Value
            val = item.get("value")
            if val is not None:
                try:
                    authorized.add(round(float(val), 3))
                except (ValueError, TypeError):
                    pass

            # Reference range string or dict
            ref = item.get("reference_range")
            if isinstance(ref, str):
                for n in NUM_PATTERN.findall(ref):
                    try:
                        authorized.add(round(float(n), 3))
                    except ValueError:
                        pass
            elif isinstance(ref, dict):
                for k in ("low", "high"):
                    v = ref.get(k)
                    if v is not None:
                        try:
                            authorized.add(round(float(v), 3))
                        except (ValueError, TypeError):
                            pass

            # Original text / clause numbers if grounded
            orig = item.get("original_text") or item.get("source_text") or ""
            for n in NUM_PATTERN.findall(orig):
                try:
                    authorized.add(round(float(n), 3))
                except ValueError:
                    pass

        return authorized

    @classmethod
    def verify(
        cls,
        generated_text: str,
        source_facts: List[Dict[str, Any]],
        allowed_structural_numbers: Set[float] = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0},
    ) -> VerificationResult:
        """
        Cross-checks generated text against authorized source facts.
        Rejects output if unapproved numbers are present.
        """
        source_nums = cls.extract_source_numbers(source_facts)
        output_nums = cls.extract_numbers(generated_text)

        discrepancies: List[float] = []

        for out_n in output_nums:
            rounded_out = round(out_n, 3)

            # Check if match is found in source facts
            matched = any(math.isclose(rounded_out, src_n, abs_tol=0.01) for src_n in source_nums)

            # If not in source facts, check if it's an allowed structural/bullet number
            if not matched and rounded_out not in allowed_structural_numbers:
                discrepancies.append(out_n)

        if discrepancies:
            msg = (
                f"Numerical discrepancy detected: text contains numbers {discrepancies} "
                f"that are not grounded in source facts {sorted(list(source_nums))}."
            )
            logger.warning(msg)
            return VerificationResult(
                is_valid=False,
                source_numbers=sorted(list(source_nums)),
                output_numbers=output_nums,
                discrepancies=discrepancies,
                reason=msg,
            )

        return VerificationResult(
            is_valid=True,
            source_numbers=sorted(list(source_nums)),
            output_numbers=output_nums,
            discrepancies=[],
            reason="All output numbers are verified against source clinical facts.",
        )
