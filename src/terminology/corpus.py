"""
Local Medical Abbreviation & Terminology Corpus loader for ClinRESET.
Parses authoritative reference corpus (ASE, MedlinePlus, Merck Manual, NCI SEER)
and resolves clinical abbreviations with domain disambiguation.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Optional

from .models import CandidateConcept, ResolutionContext

logger = logging.getLogger(__name__)

# Default path relative to project root
DEFAULT_CORPUS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "reference",
    "ClinRESET_medical_abbreviation_terminology_corpus.txt",
)


class LocalCorpus:
    """In-memory index of verified clinical abbreviations and domain mappings."""

    def __init__(self, corpus_path: Optional[str] = None):
        self.corpus_path = corpus_path or DEFAULT_CORPUS_PATH
        # Map: lowercase_abbr -> List[CandidateConcept]
        self.abbreviations: Dict[str, List[CandidateConcept]] = {}
        self._load_corpus()

    def _load_corpus(self):
        if not os.path.exists(self.corpus_path):
            logger.warning(f"Terminology corpus file not found at: {self.corpus_path}")
            return

        in_entries = False
        with open(self.corpus_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("ENTRIES"):
                    in_entries = True
                    continue

                if not in_entries or line.startswith("="):
                    continue

                # Parse: ABBREVIATION | EXPANSION | DOMAIN / CONTEXT
                if "|" in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 2:
                        abbr = parts[0]
                        expansion = parts[1]
                        domain = parts[2] if len(parts) >= 3 else "general"

                        # Handle slash or compound abbreviation
                        key = abbr.lower()
                        concept = CandidateConcept(
                            term=expansion,
                            domain=domain,
                            source="ClinRESET_corpus",
                        )

                        if key not in self.abbreviations:
                            self.abbreviations[key] = []
                        self.abbreviations[key].append(concept)

        logger.info(f"Loaded {len(self.abbreviations)} abbreviations from local corpus.")

    def lookup(
        self,
        surface_term: str,
        context: Optional[ResolutionContext] = None,
    ) -> Optional[CandidateConcept]:
        """
        Looks up a surface term or abbreviation.
        If multiple meanings exist, attempts domain-aware disambiguation.
        """
        if not surface_term:
            return None

        clean = surface_term.strip().lower()
        candidates = self.abbreviations.get(clean)
        if not candidates:
            # Try stripping trailing periods or spaces e.g. "w.n.l." -> "wnl"
            stripped = re.sub(r"\.", "", clean)
            candidates = self.abbreviations.get(stripped)

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        # Multi-candidate disambiguation
        if context:
            # Check report type match (e.g. echo, ct, ultrasound, general)
            if context.report_type:
                rt = context.report_type.lower()
                for c in candidates:
                    if rt in c.domain.lower() or c.domain.lower() in rt:
                        return c

            # Check section or nearby text
            blob = f"{context.section_title or ''} {context.nearby_text or ''}".lower()
            for c in candidates:
                # If domain keywords appear in nearby text
                domain_tokens = [t for t in re.split(r"[/ ]", c.domain.lower()) if len(t) > 3]
                if any(dt in blob for dt in domain_tokens):
                    return c

        # Default to the first entry if ambiguous
        return candidates[0]

    def has_term(self, term: str) -> bool:
        """Returns True if the abbreviation is in the local corpus."""
        clean = term.strip().lower()
        return clean in self.abbreviations or re.sub(r"\.", "", clean) in self.abbreviations
