"""
clinical_extraction/terminology/resolver.py

Contextual terminology resolution and abbreviation disambiguation engine.

Implements an 8-level hierarchical contextual resolution algorithm to disambiguate
medical abbreviations without speculative clinical interpretation:
1. report_type
2. section_title
3. nearby_text
4. anatomy_context
5. measurement_context
6. existing Phase 3 extracted entities
7. existing relationships
8. domain-specific terminology mappings
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from clinical_extraction.terminology.corpus_loader import (
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

logger = logging.getLogger("clinical_extraction.terminology.resolver")

# Non-applicable tokens (units, symbols, pure numbers)
NOT_APPLICABLE_TOKENS = {
    "%", "cm", "mm", "m/s", "mmhg", "g/dl", "mg/dl", "u/l", "iu/l", "pg/ml",
    "fl", "pg", "bpm", "kg", "lbs", "cm2", "ml", "ml/m2", "meq/l", "x", "-", "+",
    "n/a", "na",
}

# Domain keyword associations for scoring
DOMAIN_KEYWORD_MAP: dict[str, set[str]] = {
    "echocardiography": {
        "echo", "echocardiogram", "echocardiography", "cardiac", "cardio", "heart",
        "atrium", "atrial", "ventricle", "ventricular", "valve", "valvular", "mitral",
        "aortic", "tricuspid", "pulmonic", "pulmonary artery", "ejection fraction",
        "doppler", "myocardial", "infarction", "coronary", "pericardial", "wall motion",
        "septum", "septal", "regurgitation", "stenosis", "tapse", "pasp", "lvef", "lvh",
        "lvdd", "rwma", "cad", "chf", "aorta", "chambers", "dimensions",
    },
    "cardiovascular": {
        "heart", "cardiac", "cardiovascular", "coronary", "vascular", "artery", "vein",
        "blood pressure", "hypertension", "infarction", "angina", "ischemia", "stent",
        "bypass", "cabg", "myocardial",
    },
    "neurology": {
        "neuro", "neurology", "neurological", "brain", "cns", "cerebral", "spine",
        "spinal", "nerve", "cranial", "sclerosis", "stroke", "cva", "tia", "seizure",
        "eeg", "mri brain", "headache", "motor", "sensory", "reflex", "dementia",
    },
    "rheumatology": {
        "rheumatology", "rheumatoid", "joint", "joints", "arthritis", "synovial",
        "lupus", "autoimmune", "ana", "esr", "bone", "cartilage", "knee", "hip",
        "wrist", "hands", "connective",
    },
    "oncology": {
        "oncology", "cancer", "tumor", "neoplasm", "malignant", "malignancy",
        "metastasis", "metastatic", "carcinoma", "biopsy", "chemotherapy",
        "radiation", "staging", "tnm", "lesion", "radium", "mass", "lymphoma",
    },
    "laboratory": {
        "lab", "laboratory", "serum", "plasma", "blood test", "calcium", "electrolyte",
        "electrolytes", "phosphorus", "potassium", "sodium", "mg/dl", "mmol/l", "panel",
        "chem", "urinalysis", "bilirubin", "creatinine",
    },
    "hematology": {
        "hematology", "cbc", "rbc", "wbc", "platelet", "platelets", "hemoglobin",
        "hematocrit", "coagulation", "inr", "pt", "ptt", "anemia", "leukocyte",
    },
    "pulmonary": {
        "pulmonary", "respiratory", "lung", "lungs", "chest", "airway", "copd",
        "asthma", "embolism", "pleural", "bronchial", "oxygen", "pft",
    },
    "radiology": {
        "radiology", "imaging", "x-ray", "ct", "mri", "ultrasound", "scan", "view",
        "posteroanterior", "lateral", "contrast", "radiograph",
    },
    "medication": {
        "medication", "drug", "dose", "dosing", "oral", "intravenous", "iv", "po",
        "tablet", "mg", "sulfate", "morphine", "magnesium", "infusion",
    },
}

# Anatomical terms mapped to clinical domains
ANATOMY_DOMAIN_MAP: dict[str, set[str]] = {
    "right atrium": {"echocardiography", "cardiovascular"},
    "left atrium": {"echocardiography", "cardiovascular"},
    "right ventricle": {"echocardiography", "cardiovascular"},
    "left ventricle": {"echocardiography", "cardiovascular"},
    "mitral valve": {"echocardiography", "cardiovascular"},
    "aortic valve": {"echocardiography", "cardiovascular"},
    "tricuspid valve": {"echocardiography", "cardiovascular"},
    "pulmonary valve": {"echocardiography", "cardiovascular"},
    "pulmonary artery": {"echocardiography", "cardiovascular", "pulmonary"},
    "interatrial septum": {"echocardiography", "cardiovascular"},
    "interventricular septum": {"echocardiography", "cardiovascular"},
    "aortic root": {"echocardiography", "cardiovascular"},
    "pericardium": {"echocardiography", "cardiovascular"},
}

# Explicit candidate terms to specific domain mappings
TERM_SPECIFIC_DOMAINS: dict[str, set[str]] = {
    "mitral stenosis": {"echocardiography", "cardiovascular"},
    "multiple sclerosis": {"neurology"},
    "morphine sulfate": {"medication"},
    "magnesium sulfate": {"medication"},
    "right atrium": {"echocardiography", "cardiovascular"},
    "rheumatoid arthritis": {"rheumatology"},
    "radium": {"oncology"},
    "cancer": {"oncology"},
    "calcium": {"laboratory"},
    "pulmonary artery": {"echocardiography", "cardiovascular", "pulmonary"},
    "posteroanterior": {"radiology"},
    "physician assistant": {"clinical_setting"},
    "physical therapy": {"rehabilitation"},
    "prothrombin time": {"hematology", "laboratory"},
    "patient": {"clinical_setting"},
    "physical examination": {"clinical_setting"},
    "pulmonary embolism": {"pulmonary", "cardiovascular"},
    "progesterone receptor": {"oncology"},
    "partial response": {"oncology"},
    "pulse": {"vital_signs", "cardiovascular"},
    "phosphorus": {"laboratory"},
    "pressure": {"vital_signs"},
}


class TerminologyResolver:
    """
    Subsystem responsible for resolving abbreviations to standard concepts
    using an 8-level contextual hierarchy.
    """

    def __init__(self, corpus: Optional[TerminologyCorpus] = None):
        self.corpus = corpus or get_corpus()

    def _is_not_applicable(self, surface_form: str) -> bool:
        """Check if surface form is numeric, punctuation, or basic unit."""
        clean = surface_form.strip().lower()
        if not clean:
            return True
        if clean in NOT_APPLICABLE_TOKENS:
            return True
        if re.match(r"^[\d\.\,\:\;\-\+\/\%\*\#\s]+$", clean):
            return True
        return False

    def _get_candidate_domain_tags(self, candidate: CandidateConcept) -> set[str]:
        """Extract matching domain tags for a candidate concept."""
        c_term = candidate.term.lower().strip()
        c_dom = candidate.domain.lower()

        # Check explicit term mapping first
        if c_term in TERM_SPECIFIC_DOMAINS:
            return set(TERM_SPECIFIC_DOMAINS[c_term])

        # Check anatomy domain map
        if c_term in ANATOMY_DOMAIN_MAP:
            return set(ANATOMY_DOMAIN_MAP[c_term])

        tags = set()
        # Derive from domain keyword matches in term
        for dom, kws in DOMAIN_KEYWORD_MAP.items():
            for kw in kws:
                if kw in c_term:
                    tags.add(dom)
                    break

        # If still empty, derive from candidate.domain
        if not tags:
            for dom, kws in DOMAIN_KEYWORD_MAP.items():
                if dom in c_dom:
                    tags.add(dom)

        return tags

    def _score_candidate(
        self,
        candidate: CandidateConcept,
        context: ResolutionContext,
    ) -> tuple[float, list[str]]:
        """
        Evaluate candidate against the 8-level resolution hierarchy.

        Returns (score, list_of_matching_signals).
        """
        score = 0.0
        signals: list[str] = []
        cand_term_lower = candidate.term.lower().strip()
        cand_domain_tags = self._get_candidate_domain_tags(candidate)

        # -------------------------------------------------------------
        # Level 1: report_type (weight: 50.0)
        # -------------------------------------------------------------
        if context.report_type:
            rt_lower = context.report_type.strip().lower()

            # Direct match
            if rt_lower in cand_domain_tags:
                score += 50.0
                signals.append(f"Level 1 (report_type={context.report_type} match: +50.0)")
            elif rt_lower == "echocardiography" and "cardiovascular" in cand_domain_tags:
                score += 50.0
                signals.append(f"Level 1 (report_type=echocardiography matches cardiovascular domain: +50.0)")
            elif cand_domain_tags:
                # If candidate is from an opposing clinical specialty
                if not (cand_domain_tags & {rt_lower, "cardiovascular", "general"}):
                    score -= 20.0
                    signals.append(f"Level 1 (domain mismatch with {context.report_type}: -20.0)")

        # -------------------------------------------------------------
        # Level 2: section title (weight: 25.0)
        # -------------------------------------------------------------
        if context.section_title:
            st_lower = context.section_title.strip().lower()
            st_words = set(re.findall(r"\b\w+\b", st_lower))

            matched_sec = False
            # Check domain keywords in section title
            for tag in cand_domain_tags:
                kws = DOMAIN_KEYWORD_MAP.get(tag, set())
                if st_words & kws or any(kw in st_lower for kw in kws):
                    matched_sec = True
                    break

            # Check candidate term words in section title
            cand_words = set(re.findall(r"\b\w+\b", cand_term_lower)) - {"of", "and", "the", "in", "to", "or"}
            if cand_words & st_words:
                matched_sec = True

            if matched_sec:
                score += 25.0
                signals.append(f"Level 2 (section_title='{context.section_title}' match: +25.0)")

        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # Level 3: nearby terminology (weight: 15.0 - 25.0)
        # -------------------------------------------------------------
        if context.nearby_text:
            nt_lower = context.nearby_text.strip().lower()
            cand_words = set(re.findall(r"\b\w+\b", cand_term_lower)) - {"of", "and", "the", "in", "to", "or"}
            # Count word matches in nearby text
            matched_words = [w for w in cand_words if len(w) > 2 and w in nt_lower]
            if matched_words:
                nearby_score = min(20.0, len(matched_words) * 10.0)
                score += nearby_score
                signals.append(f"Level 3 (nearby_text matched {matched_words}: +{nearby_score:.1f})")

            # Check domain keywords in nearby text
            for tag in cand_domain_tags:
                kws = DOMAIN_KEYWORD_MAP.get(tag, set())
                matched_kws = [kw for kw in kws if len(kw) > 3 and kw in nt_lower]
                if matched_kws:
                    kw_score = min(15.0, len(matched_kws) * 7.5)
                    score += kw_score
                    signals.append(f"Level 3 (nearby_text domain keywords {matched_kws[:2]}: +{kw_score:.1f})")
                    break

        # -------------------------------------------------------------
        # Level 4: anatomy context (weight: 10.0 - 15.0)
        # -------------------------------------------------------------
        if context.anatomy_context:
            for anat in context.anatomy_context:
                anat_lower = anat.lower()
                if cand_term_lower in anat_lower or anat_lower in cand_term_lower:
                    score += 15.0
                    signals.append(f"Level 4 (anatomy '{anat}' matches candidate: +15.0)")
                    break
                # Anatomy domain check
                if anat_lower in ANATOMY_DOMAIN_MAP:
                    anat_domains = ANATOMY_DOMAIN_MAP[anat_lower]
                    if cand_domain_tags & anat_domains:
                        score += 7.5
                        signals.append(f"Level 4 (anatomy '{anat}' domain matches candidate: +7.5)")
                        break

        # -------------------------------------------------------------
        # Level 5: measurement context (weight: 15.0 - 20.0)
        # -------------------------------------------------------------
        if context.measurement_context:
            for meas in context.measurement_context:
                meas_lower = meas.lower()
                if cand_term_lower in meas_lower or meas_lower in cand_term_lower:
                    score += 20.0
                    signals.append(f"Level 5 (measurement '{meas}' matches candidate: +20.0)")
                    break
                # Check domain keywords in measurement
                for tag in cand_domain_tags:
                    kws = DOMAIN_KEYWORD_MAP.get(tag, set())
                    if any(kw in meas_lower for kw in kws):
                        score += 10.0
                        signals.append(f"Level 5 (measurement '{meas}' matches candidate domain: +10.0)")
                        break

        # -------------------------------------------------------------
        # Level 6: existing Phase 3 extracted entities (weight: 5.0)
        # -------------------------------------------------------------
        if context.extracted_entities:
            for ent in context.extracted_entities:
                ent_text = getattr(ent, "text", str(ent)).lower()
                if cand_term_lower in ent_text or (len(ent_text) > 3 and ent_text in cand_term_lower):
                    score += 5.0
                    signals.append(f"Level 6 (extracted entity '{ent_text}' matches candidate: +5.0)")
                    break

        # -------------------------------------------------------------
        # Level 7: existing relationships (weight: 4.0)
        # -------------------------------------------------------------
        if context.relationships:
            for rel in context.relationships:
                src = getattr(rel, "source", "").lower()
                tgt = getattr(rel, "target", "").lower()
                if cand_term_lower in src or cand_term_lower in tgt:
                    score += 4.0
                    signals.append(f"Level 7 (relationship {src}->{tgt} matches candidate: +4.0)")
                    break

        # -------------------------------------------------------------
        # Level 8: domain-specific terminology mappings (weight: 3.0)
        # -------------------------------------------------------------
        if context.domain_mappings:
            for abbr_key, mapped_val in context.domain_mappings.items():
                if mapped_val.strip().lower() == cand_term_lower:
                    score += 3.0
                    signals.append(f"Level 8 (domain mapping '{abbr_key}'->'{mapped_val}': +3.0)")
                    break

        return score, signals

    def resolve(
        self,
        surface_form: str,
        context: Optional[ResolutionContext] = None,
        report_type: Optional[str] = None,
        section_title: Optional[str] = None,
        nearby_text: Optional[str] = None,
    ) -> ResolutionResult:
        """
        Normalize and disambiguate a surface form using contextual signals.

        Parameters
        ----------
        surface_form:
            Verbatim token/abbreviation from the source report.
        context:
            Full ResolutionContext, or constructed on-the-fly from arguments.
        report_type:
            Optional report type shortcut (e.g. 'echocardiography').
        section_title:
            Optional section title shortcut.
        nearby_text:
            Optional nearby text window.

        Returns
        -------
        ResolutionResult
            Normalized concept, ambiguity flags, candidate list, and provenance.
        """
        if not surface_form:
            return ResolutionResult(
                text=surface_form,
                normalized=None,
                ambiguity=False,
                ambiguity_status=AmbiguityStatus.NOT_APPLICABLE,
                provenance="empty_input",
            )

        # Build context if not provided
        if context is None:
            context = ResolutionContext(
                report_type=report_type,
                section_title=section_title,
                nearby_text=nearby_text,
            )
        elif report_type and not context.report_type:
            context.report_type = report_type

        # 1. Non-applicable check (numbers, punctuation, units)
        if self._is_not_applicable(surface_form):
            return ResolutionResult(
                text=surface_form,
                normalized=None,
                ambiguity=False,
                ambiguity_status=AmbiguityStatus.NOT_APPLICABLE,
                provenance="non_applicable_token",
            )

        clean_key = surface_form.strip().lower()

        # Check safety list membership
        is_safety = clean_key in SAFETY_ABBREVIATIONS
        safety_alert = None
        if is_safety:
            safety_alert = f"Joint Commission 'Do Not Use' / error-prone abbreviation: '{surface_form}'"

        # 2. Look up in corpus
        record: Optional[TerminologyRecord] = self.corpus.lookup(clean_key)

        # If not in corpus, check if present in domain_mappings
        if record is None:
            if context.domain_mappings and clean_key in context.domain_mappings:
                mapped_val = context.domain_mappings[clean_key]
                return ResolutionResult(
                    text=surface_form,
                    normalized=mapped_val,
                    normalization_source="domain_specific_mappings",
                    ambiguity=False,
                    ambiguity_status=AmbiguityStatus.RESOLVED,
                    candidates=[mapped_val],
                    safety_warning=safety_alert,
                    provenance="domain_specific_dictionary",
                )

            # Not found anywhere -> UNKNOWN
            return ResolutionResult(
                text=surface_form,
                normalized=None,
                normalization_source=None,
                ambiguity=False,
                ambiguity_status=AmbiguityStatus.UNKNOWN,
                candidates=[],
                safety_warning=safety_alert,
                provenance="unknown_term_not_in_corpus",
            )

        # Candidates from corpus
        all_candidate_terms = [c.term for c in record.candidates]
        # Deduplicate terms while preserving order
        unique_candidate_terms: list[str] = []
        for t in all_candidate_terms:
            if t not in unique_candidate_terms:
                unique_candidate_terms.append(t)

        # If unambiguous (only 1 candidate and not ambiguous domain and not safety list)
        if len(record.candidates) == 1 and not record.ambiguity and not is_safety:
            return ResolutionResult(
                text=surface_form,
                normalized=record.candidates[0].term,
                normalization_source="terminology_corpus",
                ambiguity=False,
                ambiguity_status=AmbiguityStatus.RESOLVED,
                candidates=unique_candidate_terms,
                domain=record.candidates[0].domain,
                safety_warning=safety_alert,
                provenance=f"corpus_unambiguous ({record.source})",
            )

        # For ambiguous terms: evaluate each candidate concept against context
        candidate_scores: list[tuple[CandidateConcept, float, list[str]]] = []
        for cand in record.candidates:
            cand_score, cand_signals = self._score_candidate(cand, context)
            candidate_scores.append((cand, cand_score, cand_signals))

        # Sort descending by score
        candidate_scores.sort(key=lambda x: x[1], reverse=True)

        top_cand, top_score, top_signals = candidate_scores[0]
        second_score = candidate_scores[1][1] if len(candidate_scores) > 1 else -1.0

        # Decision threshold: top score must be > 0 and margin >= 10.0
        # If it's a safety abbreviation, require margin >= 15.0
        min_margin = 15.0 if is_safety else 10.0
        is_decisive = (top_score > 0.0) and (
            top_score - second_score >= min_margin or (second_score <= 0.0 and top_score >= 12.0)
        )

        if is_decisive:
            top_prov = "; ".join(top_signals[:3]) if top_signals else "context_score"
            return ResolutionResult(
                text=surface_form,
                normalized=top_cand.term,
                normalization_source="terminology_corpus",
                ambiguity=False,
                ambiguity_status=AmbiguityStatus.RESOLVED,
                candidates=unique_candidate_terms,
                domain=top_cand.domain,
                safety_warning=safety_alert,
                provenance=f"contextual_disambiguation ({top_prov})",
            )

        # Insufficient context to decide reliably -> AMBIGUOUS
        # Preserve candidates without guessing
        return ResolutionResult(
            text=surface_form,
            normalized=None,
            normalization_source="terminology_corpus",
            ambiguity=True,
            ambiguity_status=AmbiguityStatus.AMBIGUOUS,
            candidates=unique_candidate_terms,
            domain=record.domain,
            safety_warning=safety_alert,
            provenance="ambiguous_insufficient_context",
        )


# Global singleton resolver instance
_RESOLVER_INSTANCE: Optional[TerminologyResolver] = None


def get_resolver(corpus: Optional[TerminologyCorpus] = None) -> TerminologyResolver:
    """Retrieve the global TerminologyResolver singleton."""
    global _RESOLVER_INSTANCE
    if _RESOLVER_INSTANCE is None or corpus is not None:
        _RESOLVER_INSTANCE = TerminologyResolver(corpus)
    return _RESOLVER_INSTANCE
