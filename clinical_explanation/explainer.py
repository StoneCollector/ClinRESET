"""
clinical_explanation/explainer.py

Deterministic explanation generator for Phase 5A.

Transforms structured clinical concepts into patient-accessible explanations
while strictly adhering to the assertion, values, units, modifiers, and anatomy
provided by Phase 4 without speculative or prognostic interpretation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from clinical_explanation.api_lookup import lookup_term_api
from clinical_explanation.config import BIOPORTAL_API_KEY
from clinical_explanation.knowledge_base import (
    ECHO_KNOWLEDGE_BASE,
    KnowledgeBaseEntry,
    lookup_concept,
)
from clinical_explanation.models import (
    ConceptExplanation,
    ExplanationStatus,
    UnavailabilityReason,
)
from clinical_explanation.ollama_simplifier import simplify_explanation as _ollama_simplify

logger = logging.getLogger("clinical_explanation.explainer")


class ClinicalExplainer:
    """
    Deterministic clinical explanation generator.

    Consumes structured clinical concept records produced by Phase 4 and generates
    plain-language, assertion-aware explanations using the deterministic knowledge base.
    """

    def __init__(
        self,
        knowledge_base: Optional[dict[str, Any]] = None,
        bioportal_api_key: str = BIOPORTAL_API_KEY,
    ):
        self.kb = knowledge_base or ECHO_KNOWLEDGE_BASE
        self._bioportal_api_key = bioportal_api_key

    def explain_concept(self, concept_data: dict[str, Any]) -> ConceptExplanation:
        """
        Explain a single structured clinical concept record.

        Parameters
        ----------
        concept_data:
            A single concept dictionary from clinical_information["structured_clinical_concepts"].

        Returns
        -------
        ConceptExplanation:
            Validated, patient-readable explanation object.
        """
        concept_name = concept_data.get("concept") or concept_data.get("original_text", "")
        original_text = concept_data.get("original_text", concept_name)
        c_type = concept_data.get("type", "FINDING")
        category = concept_data.get("semantic_category", "OTHER_CLINICAL")
        assertion = concept_data.get("assertion", "PRESENT")
        value = concept_data.get("value")
        unit = concept_data.get("unit")
        ref_range = concept_data.get("reference_range")
        related_anatomy = list(concept_data.get("related_anatomy", []))
        modifiers = dict(concept_data.get("modifiers", {}))
        provenance = dict(concept_data.get("provenance", {}))

        ambiguity_status = provenance.get("ambiguity_status")
        is_ambiguous = provenance.get("ambiguity", False)

        # 1. Handle ambiguous concepts
        if is_ambiguous or ambiguity_status == "AMBIGUOUS":
            return ConceptExplanation(
                concept=concept_name,
                original_text=original_text,
                type=c_type,
                semantic_category=category,
                assertion=assertion,
                value=value,
                unit=unit,
                reference_range=ref_range,
                related_anatomy=related_anatomy,
                modifiers=modifiers,
                status=ExplanationStatus.EXPLANATION_UNAVAILABLE,
                explanation="Explanation unavailable: the abbreviation or term is ambiguous and has multiple clinical interpretations.",
                unavailability_reason=UnavailabilityReason.AMBIGUOUS_CONCEPT,
                provenance=provenance,
            )

        # 2. Guard: reject non-clinical concepts before any API call.
        #    Admin fields like "Registered on", "UHID", "Reg. no." should never
        #    trigger an API lookup — it would return nonsensical results.
        try:
            from clinical_extraction.filters import is_admin_field
            if is_admin_field(concept_name):
                return ConceptExplanation(
                    concept=concept_name,
                    original_text=original_text,
                    type=c_type,
                    semantic_category=category,
                    assertion=assertion,
                    value=value,
                    unit=unit,
                    reference_range=ref_range,
                    related_anatomy=related_anatomy,
                    modifiers=modifiers,
                    status=ExplanationStatus.EXPLANATION_UNAVAILABLE,
                    explanation="Explanation unavailable: non-clinical administrative field.",
                    unavailability_reason=UnavailabilityReason.UNKNOWN_CONCEPT,
                    provenance=provenance,
                )
        except ImportError:
            pass

        # 3. Handle unknown concepts — attempt API fallback before giving up.
        if ambiguity_status == "UNKNOWN" and lookup_concept(concept_name) is None:
            api_definition = lookup_term_api(
                concept_name, bioportal_api_key=self._bioportal_api_key
            )
            if api_definition is None and original_text != concept_name:
                api_definition = lookup_term_api(
                    original_text, bioportal_api_key=self._bioportal_api_key
                )

            if api_definition:
                # Build a synthetic KnowledgeBaseEntry from the API result and
                # let the normal explanation path handle it below.
                kb_entry = KnowledgeBaseEntry(
                    concept=concept_name,
                    definition=api_definition,
                    category=category,
                    anatomy="",
                    present_description=f"{concept_name} is noted in the report.",
                    absent_description=f"{concept_name}: none was reported.",
                    normal_description=f"{concept_name} is described as normal.",
                )
                logger.info(
                    "API definition used for UNKNOWN concept %r (source: DO/BioPortal)",
                    concept_name,
                )
                explanation_text = self._build_explanation_text(
                    entry=kb_entry,
                    concept_name=concept_name,
                    c_type=c_type,
                    assertion=assertion,
                    value=value,
                    unit=unit,
                    ref_range=ref_range,
                    modifiers=modifiers,
                )
                return ConceptExplanation(
                    concept=kb_entry.concept,
                    original_text=original_text,
                    type=c_type,
                    semantic_category=category,
                    assertion=assertion,
                    value=value,
                    unit=unit,
                    reference_range=ref_range,
                    related_anatomy=related_anatomy,
                    modifiers=modifiers,
                    status=ExplanationStatus.EXPLAINED,
                    explanation=explanation_text,
                    provenance=provenance,
                )

            # API also found nothing — return the unavailable message
            return ConceptExplanation(
                concept=concept_name,
                original_text=original_text,
                type=c_type,
                semantic_category=category,
                assertion=assertion,
                value=value,
                unit=unit,
                reference_range=ref_range,
                related_anatomy=related_anatomy,
                modifiers=modifiers,
                status=ExplanationStatus.EXPLANATION_UNAVAILABLE,
                explanation="Explanation unavailable: unmapped or unknown concept.",
                unavailability_reason=UnavailabilityReason.UNKNOWN_CONCEPT,
                provenance=provenance,
            )

        # 3. Lookup concept in explanation knowledge base
        kb_entry = lookup_concept(concept_name)
        if not kb_entry:
            # Fallback check against original text
            kb_entry = lookup_concept(original_text)

        # 4. API fallback — query Disease Ontology then BioPortal when the
        #    local knowledge base has no entry for this concept.
        if not kb_entry:
            api_definition = lookup_term_api(
                concept_name, bioportal_api_key=self._bioportal_api_key
            )
            # If concept_name failed, also try the raw original_text
            if api_definition is None and original_text != concept_name:
                api_definition = lookup_term_api(
                    original_text, bioportal_api_key=self._bioportal_api_key
                )

            if api_definition:
                # Wrap the API result in a minimal KnowledgeBaseEntry so the
                # existing _build_explanation_text() method works unchanged.
                kb_entry = KnowledgeBaseEntry(
                    concept=concept_name,
                    definition=api_definition,
                    category=category,
                    anatomy="",
                    present_description=f"{concept_name} is noted in the report.",
                    absent_description=f"{concept_name}: none was reported.",
                    normal_description=f"{concept_name} is described as normal.",
                )
                logger.info(
                    "API definition used for concept %r (source: DO/BioPortal)",
                    concept_name,
                )

        if not kb_entry:
            return ConceptExplanation(
                concept=concept_name,
                original_text=original_text,
                type=c_type,
                semantic_category=category,
                assertion=assertion,
                value=value,
                unit=unit,
                reference_range=ref_range,
                related_anatomy=related_anatomy,
                modifiers=modifiers,
                status=ExplanationStatus.EXPLANATION_UNAVAILABLE,
                explanation="Explanation unavailable: concept is not currently in the knowledge base.",
                unavailability_reason=UnavailabilityReason.NOT_IN_KNOWLEDGE_BASE,
                provenance=provenance,
            )

        # 4. Construct deterministic, assertion-aware explanation
        explanation_text = self._build_explanation_text(
            entry=kb_entry,
            concept_name=concept_name,
            c_type=c_type,
            assertion=assertion,
            value=value,
            unit=unit,
            ref_range=ref_range,
            modifiers=modifiers,
        )

        # 5. Ollama simplification pass
        #    Pass the raw definition (not the already-assembled sentence) to Ollama
        #    so it can rephrase in plain English. We then combine:
        #      - Ollama's plain-language explanation (replaces the technical part)
        #      - The value sentence (always appended so numbers are visible)
        ollama_status = self._infer_status(value, ref_range)
        try:
            plain = _ollama_simplify(
                concept_name=concept_name,
                technical_definition=kb_entry.definition,
                value=value,
                unit=unit,
                reference_range=ref_range,
                status=ollama_status,
            )
            if plain and plain.strip():
                # Append the value sentence so numbers always appear
                val_sentence = self._value_sentence(value, unit, ref_range)
                explanation_text = f"{plain.strip()} {val_sentence}".strip()
                logger.debug("Ollama simplified explanation used for %r", concept_name)
        except Exception as exc:
            logger.debug("Ollama simplification skipped (%s) — using deterministic text.", exc)

        return ConceptExplanation(
            concept=kb_entry.concept,
            original_text=original_text,
            type=c_type,
            semantic_category=category,
            assertion=assertion,
            value=value,
            unit=unit,
            reference_range=ref_range,
            related_anatomy=related_anatomy or ([kb_entry.anatomy] if kb_entry.anatomy else []),
            modifiers=modifiers,
            status=ExplanationStatus.EXPLAINED,
            explanation=explanation_text,
            provenance=provenance,
        )

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _infer_status(value: Optional[Any], ref_range: Optional[str]) -> str:
        """
        Derive a simple HIGH / LOW / NORMAL / UNKNOWN status by comparing
        the numeric value against a 'low - high' reference range string.
        Used to give Ollama context about the patient's result.
        """
        if value is None or ref_range is None:
            return "UNKNOWN"
        try:
            import re
            nums = re.findall(r"[\d\.]+", str(ref_range))
            if len(nums) < 2:
                return "UNKNOWN"
            low_ref, high_ref = float(nums[0]), float(nums[1])
            num_val = float(str(value))
            if num_val < low_ref:
                return "LOW"
            if num_val > high_ref:
                return "HIGH"
            return "NORMAL"
        except (ValueError, TypeError):
            return "UNKNOWN"

    @staticmethod
    def _value_sentence(value: Optional[Any], unit: Optional[str], ref_range: Optional[str]) -> str:
        """
        Build the 'The reported value is X unit [range: Y].' sentence
        that is always appended after the Ollama explanation.
        """
        if value is None:
            return ""
        unit_str = f" {unit}" if unit else ""
        ref_str = f" (reference range: {ref_range})" if ref_range else ""
        return f"The reported value is {value}{unit_str}{ref_str}."

    def _build_explanation_text(
        self,
        entry: Any,
        concept_name: str,
        c_type: str,
        assertion: str,
        value: Optional[Any],
        unit: Optional[str],
        ref_range: Optional[str],
        modifiers: dict[str, Any],
    ) -> str:
        """Assemble factual, patient-friendly sentence for the concept."""
        # 1. Measurement explanation
        if c_type == "MEASUREMENT" or value is not None:
            unit_str = f" {unit}" if unit else ""
            val_str = f"{value}{unit_str}"
            ref_str = f" (reported reference range: {ref_range})" if ref_range else ""
            meas_sentence = f"The reported value is {val_str}{ref_str}."
            return f"{entry.definition} {meas_sentence}".strip()

        # 2. Finding: ABSENT assertion
        if assertion == "ABSENT":
            if entry.absent_description:
                return f"{entry.absent_description} {entry.definition}".strip()
            return f"{entry.concept}: none was reported. {entry.definition}".strip()

        # 3. Finding: NORMAL assertion
        if assertion == "NORMAL":
            if entry.normal_description:
                return f"{entry.normal_description} {entry.definition}".strip()
            return f"{entry.concept} is described as normal. {entry.definition}".strip()

        # 4. Finding: PRESENT assertion (with modifiers if applicable)
        mod_prefix = []
        if modifiers.get("pattern"):
            mod_prefix.append(modifiers["pattern"].lower())
        if modifiers.get("grade_text"):
            mod_prefix.append(modifiers["grade_text"])
        if modifiers.get("severity_text"):
            mod_prefix.append(modifiers["severity_text"].lower())

        if mod_prefix:
            mod_label = " ".join(mod_prefix)
            # Avoid repeating e.g. "mild mild tricuspid regurgitation"
            concept_clean = entry.concept
            for p in mod_prefix:
                if concept_clean.lower().startswith(p.lower()):
                    concept_clean = concept_clean[len(p):].strip()
            lead_in = f"The report describes {mod_label} {concept_clean.lower()}."
            return f"{lead_in} {entry.definition}".strip()

        if entry.present_description:
            return f"{entry.present_description} {entry.definition}".strip()

        return f"{entry.concept} is noted in the report. {entry.definition}".strip()

    def explain_report_concepts(
        self,
        structured_concepts: list[dict[str, Any]],
    ) -> list[ConceptExplanation]:
        """
        Explain all concepts in a report while preventing duplicate explanations
        for identical findings or measurements.

        Pre-warms the API cache in parallel for all concepts that are not in the
        local knowledge base, so BioPortal is queried concurrently (5 threads)
        rather than one-by-one.
        """
        from clinical_explanation.api_lookup import batch_lookup_terms

        # Collect concept names that are not already in the local KB
        unknown_terms: list[str] = []
        for c in structured_concepts:
            name = (c.get("concept") or c.get("original_text", "")).strip()
            if name and not lookup_concept(name):
                unknown_terms.append(name)

        # Pre-warm cache in parallel (no-op for already-cached terms)
        if unknown_terms:
            logger.info(
                "Pre-warming API cache for %d unknown terms (parallel)", len(unknown_terms)
            )
            batch_lookup_terms(
                unknown_terms,
                bioportal_api_key=self._bioportal_api_key,
                max_workers=5,
            )

        # Main explain loop (all API calls now hit the warm cache instantly)
        explanations: list[ConceptExplanation] = []
        seen_keys: set[tuple[str, str, str, Any]] = set()

        for c in structured_concepts:
            key = (
                (c.get("concept") or c.get("original_text", "")).lower(),
                c.get("type", ""),
                c.get("assertion", ""),
                c.get("value"),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)

            exp = self.explain_concept(c)
            explanations.append(exp)

        return explanations
