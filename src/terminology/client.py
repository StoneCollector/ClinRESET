"""
Selective and lightweight Terminology Client for ClinRESET.
Queries free, open-access, zero-account public medical APIs:
1. EMBL-EBI OLS4 (Official SNOMED CT concepts & synonyms)
2. NIH Clinical Tables API (US NLM conditions & disorders)

Enforces strict request timeouts, SSL security, and graceful offline degradation.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TerminologyClient:
    """Client for querying open-access terminology APIs with zero authentication."""

    def __init__(self, timeout: float = 1.5, user_agent: str = "ClinRESET-Research/1.0"):
        self.timeout = timeout
        self.user_agent = user_agent

    def search_snomed(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Queries EMBL-EBI OLS4 API for SNOMED CT concept.
        Returns:
            Dict with 'snomed_id', 'preferred_term', 'layman_synonym', 'organ_system'
            or None if not found or offline.
        """
        if not query or len(query.strip()) < 3:
            return None

        clean_query = query.strip()
        encoded = urllib.parse.quote_plus(clean_query)
        url = f"https://www.ebi.ac.uk/ols4/api/search?q={encoded}&ontology=snomed&rows=2"

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return None
                data = json.loads(resp.read().decode("utf-8"))

            docs = data.get("response", {}).get("docs", [])
            if not docs:
                return None

            best = docs[0]
            obo_id = best.get("obo_id") or best.get("short_form")
            # Format: 'SNOMED:8186001' or '8186001'
            snomed_id = obo_id if obo_id else None
            if snomed_id and not snomed_id.startswith("SNOMED:"):
                snomed_id = f"SNOMED:{snomed_id}"

            preferred_term = best.get("label", clean_query.title())
            synonyms = best.get("synonym", [])
            layman_synonym = synonyms[0] if synonyms else preferred_term

            # Infer high-level organ system from term keywords
            organ_system = self._infer_organ_system(preferred_term)

            return {
                "snomed_id": snomed_id,
                "preferred_term": preferred_term,
                "layman_synonym": layman_synonym,
                "organ_system": organ_system,
                "source": "ols_snomed",
            }
        except Exception as e:
            logger.debug(f"OLS SNOMED lookup skipped for '{query}': {e}")
            return None

    def search_nih_conditions(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Secondary fallback: Queries US NIH National Library of Medicine Clinical Tables API.
        """
        if not query or len(query.strip()) < 3:
            return None

        clean_query = query.strip()
        encoded = urllib.parse.quote_plus(clean_query)
        url = f"https://clinicaltables.nlm.nih.gov/api/conditions/v3/search?terms={encoded}&maxList=1"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.user_agent},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return None
                data = json.loads(resp.read().decode("utf-8"))

            total_matches = data[0] if len(data) > 0 else 0
            if total_matches > 0 and len(data) > 3 and data[3]:
                match_name = data[3][0]
                if isinstance(match_name, list) and match_name:
                    preferred_term = match_name[1] if len(match_name) > 1 else match_name[0]
                else:
                    preferred_term = str(match_name)

                return {
                    "snomed_id": None,
                    "preferred_term": preferred_term,
                    "layman_synonym": preferred_term,
                    "organ_system": self._infer_organ_system(preferred_term),
                    "source": "nih_clinical_tables",
                }
        except Exception as e:
            logger.debug(f"NIH conditions lookup skipped for '{query}': {e}")
            return None

        return None

    @staticmethod
    def _infer_organ_system(term: str) -> str:
        """Categorizes clinical terms into anatomical organ systems."""
        t = term.lower()
        if any(w in t for w in ["heart", "cardio", "ventric", "atria", "aort", "myocard", "coronary", "valve", "pulse", "pasp"]):
            return "Cardiovascular"
        if any(w in t for w in ["lung", "pulmon", "pleura", "pneumo", "bronch", "chest", "hila", "thorac", "consolidat", "lobe"]):
            return "Respiratory"
        if any(w in t for w in ["kidney", "renal", "nephro", "bladder", "ureter", "urinary", "prostate"]):
            return "Genitourinary"
        if any(w in t for w in ["liver", "hepat", "biliary", "gall", "chole", "pancrea", "spleen", "gastric", "colon", "bowel", "intestin", "appendix"]):
            return "Gastrointestinal"
        if any(w in t for w in ["spine", "lumbar", "cervical", "vertebra", "disc", "joint", "facet", "bone", "lordosis", "spondyl", "sublux"]):
            return "Musculoskeletal"
        if any(w in t for w in ["brain", "cerebr", "cranial", "neural", "nerve"]):
            return "Neurological"
        return "General Clinical"
