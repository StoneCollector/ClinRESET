"""
clinical_explanation/api_lookup.py

Layered API fallback for clinical term definitions.

When a concept is not found in the local ECHO_KNOWLEDGE_BASE, this module
attempts to resolve a plain-English definition by querying, in order:

  1. A persistent on-disk JSON cache  (instant — no network call)
  2. Disease Ontology REST API        (fast, no API key required, diseases only)
  3. BioPortal REST API               (broader: MESH + NCIT, covers symptoms,
                                       signs, measurements; slower)

Every successful API result is written to the cache so that the same term
is never fetched from the network more than once across all report runs.

Cache file location: <project_root>/clinical_explanation/term_cache.json
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("clinical_explanation.api_lookup")

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

_CACHE_FILE = Path(__file__).resolve().parent / "term_cache.json"

# Disease Ontology — no API key required
_DO_SEARCH_URL = "https://api.disease-ontology.org/v1/terms/search"

# BioPortal — requires API key; search across MeSH and NCI Thesaurus
# (both contain symptoms, signs, measurements, and diseases)
_BIOPORTAL_SEARCH_URL = "https://data.bioontology.org/search"
_BIOPORTAL_ONTOLOGIES = "MESH,NCIT"

# Sentinel stored in cache when a term is known to have no API definition,
# so we never retry it.
_NO_RESULT_SENTINEL = "__NO_RESULT__"

# Shared lock — the background worker thread and any future concurrent
# callers both write to the same cache file.
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Persistent disk cache
# ---------------------------------------------------------------------------


def _load_cache() -> dict[str, str]:
    """Load the term cache from disk. Returns an empty dict on first run."""
    if not _CACHE_FILE.exists():
        return {}
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning("Could not read term cache (%s): %s", _CACHE_FILE, exc)
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    """Persist the in-memory cache dict to disk."""
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Could not write term cache (%s): %s", _CACHE_FILE, exc)


# ---------------------------------------------------------------------------
# Individual API callers
# ---------------------------------------------------------------------------


def _query_disease_ontology(term: str) -> Optional[str]:
    """
    Search the Human Disease Ontology for *term*.

    Returns the definition string if found, or None if the term is not a
    recognised disease / the API returns no usable result.
    """
    try:
        resp = httpx.post(
            _DO_SEARCH_URL,
            json={"data": {"names": [term]}},
            timeout=10.0,
        )
        if resp.status_code != 200:
            logger.debug("DO API returned %s for term %r", resp.status_code, term)
            return None

        results = resp.json().get("results", [])
        if not results:
            return None

        # Prefer an exact name match; fall back to the first result.
        term_lower = term.strip().lower()
        best = None
        for r in results:
            definition = r.get("definition", "").strip()
            if not definition:
                continue
            if r.get("name", "").strip().lower() == term_lower:
                best = definition
                break
            if best is None:
                best = definition

        return best or None

    except Exception as exc:
        logger.debug("DO API lookup failed for term %r: %s", term, exc)
        return None


def _query_bioportal(term: str, api_key: str) -> Optional[str]:
    """
    Search BioPortal (MESH + NCIT ontologies) for *term*.

    Returns the first non-empty definition string, or None.
    BioPortal covers diseases, symptoms, clinical signs, and measurements,
    making it a broader fallback than the Disease Ontology.
    """
    if not api_key:
        logger.debug("BioPortal API key not configured — skipping.")
        return None

    try:
        resp = httpx.get(
            _BIOPORTAL_SEARCH_URL,
            params={
                "q": term,
                "ontologies": _BIOPORTAL_ONTOLOGIES,
                "pagesize": 5,
                "require_definition": True,
            },
            headers={"Authorization": f"apikey token={api_key}"},
            timeout=20.0,
        )
        if resp.status_code != 200:
            logger.debug(
                "BioPortal API returned %s for term %r", resp.status_code, term
            )
            return None

        collection = resp.json().get("collection", [])
        if not collection:
            # retry without require_definition in case the flag filtered everything
            resp2 = httpx.get(
                _BIOPORTAL_SEARCH_URL,
                params={
                    "q": term,
                    "ontologies": _BIOPORTAL_ONTOLOGIES,
                    "pagesize": 5,
                },
                headers={"Authorization": f"apikey token={api_key}"},
                timeout=20.0,
            )
            if resp2.status_code == 200:
                collection = resp2.json().get("collection", [])

        if not collection:
            return None

        term_lower = term.strip().lower()
        best: Optional[str] = None

        for item in collection:
            label = (item.get("prefLabel") or "").strip().lower()
            definitions: list[str] = item.get("definition") or []
            if not definitions:
                continue
            definition = definitions[0].strip()
            if not definition:
                continue
            if label == term_lower:
                # Exact label match — highest priority
                return definition
            if best is None:
                best = definition

        return best

    except Exception as exc:
        logger.debug("BioPortal API lookup failed for term %r: %s", term, exc)
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def lookup_term_api(term: str, bioportal_api_key: str = "") -> Optional[str]:
    """
    Look up a clinical term definition using the layered API fallback strategy.

    Lookup order:
      1. Disk cache (instant, no network)
      2. Disease Ontology API (fast, diseases/conditions)
      3. BioPortal API (broader; symptoms, signs, measurements)

    Parameters
    ----------
    term:
        The clinical concept name to resolve (e.g. "polycystic ovary syndrome").
    bioportal_api_key:
        BioPortal API key. Pass an empty string to skip BioPortal.

    Returns
    -------
    str or None:
        A plain-English definition sentence, or None if no definition was found
        in any source.
    """
    if not term or not term.strip():
        return None

    cache_key = term.strip().lower()

    # 1. Check disk cache under a lock (cheap — just a dict lookup)
    with _cache_lock:
        cache = _load_cache()
        cached = cache.get(cache_key)

    if cached is not None:
        if cached == _NO_RESULT_SENTINEL:
            logger.debug("Cache miss (no-result sentinel) for term %r", term)
            return None
        logger.debug("Cache HIT for term %r", term)
        return cached

    # 2. Disease Ontology (no key required, fast)
    logger.info("API lookup — trying Disease Ontology for: %r", term)
    definition = _query_disease_ontology(term)

    # 3. BioPortal (broader, slower)
    if definition is None:
        logger.info("API lookup — trying BioPortal for: %r", term)
        definition = _query_bioportal(term, bioportal_api_key)

    # 4. Persist result (or sentinel) to cache
    with _cache_lock:
        cache = _load_cache()  # reload in case another thread wrote between steps
        cache[cache_key] = definition if definition is not None else _NO_RESULT_SENTINEL
        _save_cache(cache)

    if definition:
        logger.info("API lookup succeeded for term %r", term)
    else:
        logger.info("API lookup found nothing for term %r — sentinel cached", term)

    return definition


def batch_lookup_terms(
    terms: list[str],
    bioportal_api_key: str = "",
    max_workers: int = 5,
) -> dict[str, Optional[str]]:
    """
    Look up definitions for multiple clinical terms in parallel.

    Terms already in the disk cache are resolved instantly (no network call).
    Uncached terms are fetched concurrently using up to *max_workers* threads,
    reducing wall-clock time from O(n * 20s) to O(n/workers * 20s).

    Parameters
    ----------
    terms:
        List of clinical concept names to resolve.
    bioportal_api_key:
        BioPortal API key (empty string disables BioPortal).
    max_workers:
        Maximum parallel lookup threads (default: 5).

    Returns
    -------
    dict[str, Optional[str]]
        Mapping of term → definition string (or None if not found).
    """
    if not terms:
        return {}

    results: dict[str, Optional[str]] = {}

    # Split into cached (instant) and uncached (needs network)
    with _cache_lock:
        cache = _load_cache()

    cached_terms: list[str] = []
    uncached_terms: list[str] = []

    for t in terms:
        key = t.strip().lower()
        if key in cache:
            cached_terms.append(t)
            val = cache[key]
            results[t] = None if val == _NO_RESULT_SENTINEL else val
        else:
            uncached_terms.append(t)

    logger.info(
        "batch_lookup_terms: %d cached, %d to fetch (workers=%d)",
        len(cached_terms), len(uncached_terms), max_workers,
    )

    if not uncached_terms:
        return results

    # Fetch uncached terms in parallel
    with ThreadPoolExecutor(max_workers=min(max_workers, len(uncached_terms))) as pool:
        future_to_term = {
            pool.submit(lookup_term_api, t, bioportal_api_key): t
            for t in uncached_terms
        }
        for future in as_completed(future_to_term):
            term = future_to_term[future]
            try:
                results[term] = future.result()
            except Exception as exc:
                logger.warning("batch lookup failed for %r: %s", term, exc)
                results[term] = None

    return results
