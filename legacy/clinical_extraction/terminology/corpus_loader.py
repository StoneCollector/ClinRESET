"""
clinical_extraction/terminology/corpus_loader.py

Loader and indexer for ClinRESET_medical_abbreviation_terminology_corpus.txt.

Parses raw corpus entries into structured TerminologyRecord instances,
extracting candidate expansions, domain tags, safety flags, and provenance.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from clinical_extraction.terminology.models import (
    AmbiguityStatus,
    CandidateConcept,
    TerminologyRecord,
)

logger = logging.getLogger("clinical_extraction.terminology.corpus_loader")

# Path to corpus file default
DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent.parent.parent / "ClinRESET_medical_abbreviation_terminology_corpus.txt"

# Joint Commission known error-prone abbreviation forms
SAFETY_ABBREVIATIONS = {
    "u", "u/u", "iu", "qd", "q.d.", "qod", "q.o.d.", "mso4", "mgso4", "ms",
    "x.0 mg", ".x mg",
}


def _to_title_case_term(text: str) -> str:
    """Format expansion into standard clinical Title Case while preserving embedded acronyms."""
    clean = text.strip()
    if not clean:
        return clean

    words = clean.split()
    formatted_words = []
    for w in words:
        # Preserve acronyms like HIV, DNA, ECG, LV, RV
        if w.isupper() and len(w) > 1:
            formatted_words.append(w)
        elif "-" in w:
            parts = [p.capitalize() if not p.isupper() else p for p in w.split("-")]
            formatted_words.append("-".join(parts))
        elif "/" in w:
            parts = [p.capitalize() if not p.isupper() else p for p in w.split("/")]
            formatted_words.append("/".join(parts))
        else:
            formatted_words.append(w.capitalize())
    return " ".join(formatted_words)


def _split_candidate_expansions(expansion_text: str) -> list[str]:
    """Split expansion string into individual candidate concepts."""
    # Strip trailing comments like '; context required' or '(prohibited/error-prone)'
    clean = re.sub(r";\s*context required.*$", "", expansion_text, flags=re.IGNORECASE)
    clean = re.sub(r"\s*\((?:prohibited|error-prone)[^\)]*\)", "", clean, flags=re.IGNORECASE)

    if " OR " in clean:
        raw_parts = [p.strip() for p in clean.split(" OR ")]
    elif ";" in clean:
        raw_parts = [p.strip() for p in clean.split(";")]
    else:
        raw_parts = [clean.strip()]

    candidates: list[str] = []
    for p in raw_parts:
        # Clean parenthetical notes like "(amputation)" if standalone
        c = p.strip(" ,.-;")
        if c:
            candidates.append(_to_title_case_term(c))

    return candidates


class TerminologyCorpus:
    """
    In-memory indexed representation of the medical abbreviation terminology corpus.
    """

    def __init__(self, corpus_path: Optional[Path | str] = None):
        self.corpus_path = Path(corpus_path) if corpus_path else DEFAULT_CORPUS_PATH
        self.raw_record_count: int = 0
        self.records_by_surface_form: dict[str, TerminologyRecord] = {}
        self.report_specific_mappings_count: int = 0
        self.ambiguous_records_count: int = 0
        self._load()

    def _load(self) -> None:
        """Parse corpus file into structured in-memory records."""
        if not self.corpus_path.exists():
            logger.warning("Terminology corpus file not found at: %s", self.corpus_path)
            return

        with open(self.corpus_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        in_entries = False
        raw_count = 0
        intermediate_map: dict[str, list[tuple[int, str, str, str]]] = {}

        for line_idx, line in enumerate(lines):
            line_str = line.strip()
            if line_str == "ENTRIES":
                in_entries = True
                continue
            if not in_entries or not line_str or line_str.startswith("==="):
                continue

            parts = [p.strip() for p in line_str.split("|")]
            if len(parts) >= 2:
                raw_count += 1
                surface = parts[0]
                expansion = parts[1]
                domain = parts[2] if len(parts) > 2 else "general"

                # Handle slashed surface forms (e.g. "BID/bid", "SQ/SUBQ", "LN(S)")
                surfaces_to_index = [surface]
                if "/" in surface and not any(c in surface for c in (" ", "0", "1", "2")):
                    sub_surfs = [s.strip() for s in surface.split("/")]
                    surfaces_to_index.extend(sub_surfs)

                for s_form in surfaces_to_index:
                    s_key = s_form.lower().strip()
                    if s_key:
                        if s_key not in intermediate_map:
                            intermediate_map[s_key] = []
                        intermediate_map[s_key].append((line_idx + 1, s_form, expansion, domain))

        self.raw_record_count = raw_count

        # Build consolidated TerminologyRecord per unique surface form
        ambig_count = 0
        report_spec_count = 0

        for s_key, entries in intermediate_map.items():
            primary_surface = entries[0][1]
            candidates: list[CandidateConcept] = []
            seen_terms: set[str] = set()
            domains: set[str] = set()
            sources: list[str] = []
            has_ambig_domain = False

            is_safety = s_key in SAFETY_ABBREVIATIONS

            for line_no, _, exp_raw, dom_raw in entries:
                sources.append(f"line {line_no}")
                dom_clean = dom_raw.strip().lower()
                domains.add(dom_clean)

                if "ambiguous" in dom_clean or "safety list" in dom_clean:
                    has_ambig_domain = True

                # Check if report specific domain
                if any(k in dom_clean for k in (
                    "echocardiography", "hematology", "liver", "renal",
                    "endocrine", "cardiovascular", "radiology", "ecg"
                )):
                    report_spec_count += 1

                extracted_cands = _split_candidate_expansions(exp_raw)
                for cand_term in extracted_cands:
                    cand_lower = cand_term.lower()
                    if cand_lower not in seen_terms:
                        seen_terms.add(cand_lower)
                        candidates.append(
                            CandidateConcept(
                                term=cand_term,
                                domain=dom_clean,
                                source=f"ClinRESET_corpus:L{line_no}",
                                is_safety_warning=is_safety or ("safety list" in dom_clean),
                            )
                        )

            is_ambiguous = len(candidates) > 1 or has_ambig_domain or is_safety
            if is_ambiguous:
                ambig_count += 1
                ambig_status = AmbiguityStatus.AMBIGUOUS
                normalized_term = None
            else:
                ambig_status = AmbiguityStatus.RESOLVED
                normalized_term = candidates[0].term if candidates else None

            primary_domain = "/".join(sorted(domains)) if domains else "general"
            provenance_src = f"ClinRESET_medical_abbreviation_terminology_corpus.txt ({', '.join(sources[:2])})"

            record = TerminologyRecord(
                surface_form=primary_surface,
                normalized_term=normalized_term,
                domain=primary_domain,
                candidates=candidates,
                ambiguity=is_ambiguous,
                ambiguity_status=ambig_status,
                source=provenance_src,
                confidence="source-backed",
            )
            self.records_by_surface_form[s_key] = record

        self.ambiguous_records_count = ambig_count
        self.report_specific_mappings_count = report_spec_count

        logger.info(
            "Terminology corpus loaded: %d raw records, %d unique surface forms, "
            "%d ambiguous records, %d report-specific mappings",
            self.raw_record_count,
            len(self.records_by_surface_form),
            self.ambiguous_records_count,
            self.report_specific_mappings_count,
        )

    def lookup(self, surface_form: str) -> Optional[TerminologyRecord]:
        """Case-insensitive lookup of a surface form."""
        if not surface_form:
            return None
        clean_key = surface_form.strip().lower()
        return self.records_by_surface_form.get(clean_key)


# Global singleton cache
_CORPUS_INSTANCE: Optional[TerminologyCorpus] = None


def get_corpus(corpus_path: Optional[Path | str] = None) -> TerminologyCorpus:
    """Retrieve the global TerminologyCorpus singleton instance."""
    global _CORPUS_INSTANCE
    if _CORPUS_INSTANCE is None or corpus_path is not None:
        _CORPUS_INSTANCE = TerminologyCorpus(corpus_path)
    return _CORPUS_INSTANCE
