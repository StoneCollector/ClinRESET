"""
Unified Terminology Normalizer for ClinRESET.
Implements the Offline-First with Dynamic Cache Enrichment pattern:
1. Local Abbreviation expansion via LocalCorpus (instant)
2. Local Persistent Cache lookup via terminology_cache.json (0.001ms)
3. Opportunistic API lookup via EMBL-EBI OLS / NIH Clinical Tables (only when online)
4. Auto-saves newly learned terms to local cache (learned forever!)
5. Strict isolation of unknown terms with is_known=False.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List, Optional

from .client import TerminologyClient
from .corpus import LocalCorpus
from .models import NormalizedConcept, ResolutionContext

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "terminology_cache.json",
)


class TerminologyNormalizer:
    """Normalizes clinical terms into standardized SNOMED concepts, layman descriptions, and organ systems."""

    def __init__(
        self,
        cache_path: Optional[str] = None,
        corpus_path: Optional[str] = None,
        online: bool = True,
        client: Optional[TerminologyClient] = None,
    ):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.online = online
        self.corpus = LocalCorpus(corpus_path=corpus_path)
        self.client = client or TerminologyClient()

        # In-memory dictionary: lowercase_term -> dict of normalized properties
        self.cache: Dict[str, Dict[str, Optional[str]]] = {}
        self._dirty_cache: bool = False
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.cache = {k.lower(): v for k, v in data.items() if isinstance(v, dict)}
                logger.info(f"Loaded {len(self.cache)} cached terminology records from {self.cache_path}")
            except Exception as e:
                logger.warning(f"Could not load terminology cache: {e}")
                self.cache = {}

    def save_cache(self):
        """Persists learned terminology to disk so it is available offline forever."""
        if not self._dirty_cache:
            return

        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
            self._dirty_cache = False
            logger.info(f"Successfully saved updated terminology cache to {self.cache_path}")
        except Exception as e:
            logger.error(f"Failed to save terminology cache: {e}")

    def normalize(
        self,
        term: str,
        context: Optional[ResolutionContext] = None,
    ) -> NormalizedConcept:
        """
        Normalizes a clinical finding concept.
        Returns a NormalizedConcept with canonical term, SNOMED code, layman synonym, and is_known flag.
        """
        if not term or not term.strip():
            return NormalizedConcept(
                raw_term="",
                preferred_term="",
                is_known=False,
                source="unmapped",
                confidence=0.0,
            )

        raw = term.strip()
        clean = re.sub(r"^[ \t:.-]+|[ \t:.-]+$", "", raw).strip()
        clean_lower = clean.lower()

        # 1. Check local abbreviation corpus first (e.g. 'MPD' -> 'Main pancreatic duct')
        expanded_term = clean
        corpus_match = self.corpus.lookup(clean_lower, context=context)
        source = "unmapped"

        if corpus_match:
            expanded_term = corpus_match.term
            source = "abbreviation_corpus"

        lookup_key = expanded_term.lower()

        # 2. Check local persistent cache (0.001ms instant)
        if lookup_key in self.cache:
            cached = self.cache[lookup_key]
            return NormalizedConcept(
                raw_term=raw,
                preferred_term=cached.get("preferred_term", expanded_term.title()),
                snomed_id=cached.get("snomed_id"),
                radlex_id=cached.get("radlex_id"),
                layman_synonym=cached.get("layman_synonym"),
                organ_system=cached.get("organ_system", "General Clinical"),
                is_known=True,
                source="local_cache",
                confidence=1.0,
            )

        # Also check raw term in cache if different from expanded term
        if clean_lower in self.cache:
            cached = self.cache[clean_lower]
            return NormalizedConcept(
                raw_term=raw,
                preferred_term=cached.get("preferred_term", clean.title()),
                snomed_id=cached.get("snomed_id"),
                radlex_id=cached.get("radlex_id"),
                layman_synonym=cached.get("layman_synonym"),
                organ_system=cached.get("organ_system", "General Clinical"),
                is_known=True,
                source="local_cache",
                confidence=1.0,
            )

        # 3. Dynamic API Query (Only for plausible atomic concepts when online)
        words = expanded_term.split()
        is_candidate_for_api = (
            self.online
            and 1 <= len(words) <= 4
            and 3 <= len(expanded_term) <= 35
            and not any(ch in expanded_term for ch in ["&", "/", "?", ";", ":", "\\", "\n", "\r", "%"])
        )

        if is_candidate_for_api:
            # Query EBI OLS SNOMED
            api_res = self.client.search_snomed(expanded_term)
            if not api_res and expanded_term != clean:
                api_res = self.client.search_snomed(clean)

            # Fallback to NIH clinical tables
            if not api_res:
                api_res = self.client.search_nih_conditions(expanded_term)

            if api_res:
                pref = api_res.get("preferred_term", expanded_term.title())
                snomed = api_res.get("snomed_id")
                layman = api_res.get("layman_synonym", pref)
                organ = api_res.get("organ_system", "General Clinical")
                api_source = api_res.get("source", "ols_snomed")

                # Auto-save newly learned term into persistent cache
                self.cache[lookup_key] = {
                    "preferred_term": pref,
                    "snomed_id": snomed,
                    "radlex_id": None,
                    "layman_synonym": layman,
                    "organ_system": organ,
                    "is_known": True,
                }
                self._dirty_cache = True
                self.save_cache()

                return NormalizedConcept(
                    raw_term=raw,
                    preferred_term=pref,
                    snomed_id=snomed,
                    layman_synonym=layman,
                    organ_system=organ,
                    is_known=True,
                    source=api_source,
                    confidence=0.95,
                )
            else:
                # Negative cache: remember this term was checked and unmapped
                self.cache[lookup_key] = {
                    "preferred_term": expanded_term.title(),
                    "snomed_id": None,
                    "radlex_id": None,
                    "layman_synonym": expanded_term,
                    "organ_system": TerminologyClient._infer_organ_system(expanded_term),
                    "is_known": False,
                }
                self._dirty_cache = True

        # 4. If expanded from corpus but no SNOMED entry, it is still a known clinical term!
        if corpus_match:
            organ = TerminologyClient._infer_organ_system(expanded_term)
            return NormalizedConcept(
                raw_term=raw,
                preferred_term=expanded_term,
                snomed_id=None,
                layman_synonym=expanded_term,
                organ_system=organ,
                is_known=True,
                source="abbreviation_corpus",
                confidence=0.9,
            )

        # 5. Unknown concept isolation: flag as is_known=False
        organ = TerminologyClient._infer_organ_system(clean)
        return NormalizedConcept(
            raw_term=raw,
            preferred_term=clean.title(),
            snomed_id=None,
            radlex_id=None,
            layman_synonym=None,
            organ_system=organ,
            is_known=False,
            source="unmapped",
            confidence=0.3,
        )

    def normalize_batch(
        self,
        terms: List[str],
        context: Optional[ResolutionContext] = None,
    ) -> List[NormalizedConcept]:
        """Normalizes a batch of terms."""
        return [self.normalize(t, context=context) for t in terms]
