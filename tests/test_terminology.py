"""
Unit and integration tests for ClinRESET Terminology Normalization subsystem (Phase 5).
Tests abbreviation expansion, local cache retrieval, SNOMED resolution,
organ system categorization, and unknown concept isolation.
"""

import os
import pytest
from src.terminology.models import NormalizedConcept, ResolutionContext
from src.terminology.corpus import LocalCorpus
from src.terminology.client import TerminologyClient
from src.terminology.normalizer import TerminologyNormalizer


def test_local_corpus_abbreviation_expansion():
    corpus = LocalCorpus()

    # COPD
    match_copd = corpus.lookup("COPD")
    assert match_copd is not None
    assert "pulmonary" in match_copd.term.lower()

    # CHF
    match_chf = corpus.lookup("CHF")
    assert match_chf is not None
    assert "heart failure" in match_chf.term.lower()

    # CXR (Chest x-ray)
    match_cxr = corpus.lookup("cxr")
    assert match_cxr is not None
    assert "x-ray" in match_cxr.term.lower()


def test_local_corpus_context_disambiguation():
    corpus = LocalCorpus()

    # Ambiguous abbreviation CA (Cancer vs Calcium)
    ctx_onco = ResolutionContext(report_type="oncology", section_title="TUMOR BOARD")
    match_onco = corpus.lookup("CA", context=ctx_onco)
    assert match_onco is not None

    ctx_lab = ResolutionContext(report_type="laboratory", section_title="BIOCHEMISTRY")
    match_lab = corpus.lookup("CA", context=ctx_lab)
    assert match_lab is not None


def test_normalizer_cached_concepts_offline():
    # Force offline mode to guarantee pure local retrieval
    normalizer = TerminologyNormalizer(online=False)

    # 1. Cardiomegaly
    norm_cardio = normalizer.normalize("cardiomegaly")
    assert norm_cardio.is_known is True
    assert norm_cardio.snomed_id == "SNOMED:8186001"
    assert "heart" in norm_cardio.layman_synonym.lower()
    assert norm_cardio.organ_system == "Cardiovascular"

    # 2. Pleural effusion
    norm_eff = normalizer.normalize("pleural effusion")
    assert norm_eff.is_known is True
    assert norm_eff.snomed_id == "SNOMED:60046008"
    assert norm_eff.organ_system == "Respiratory"

    # 3. Pneumothorax
    norm_ptx = normalizer.normalize("pneumothorax")
    assert norm_ptx.is_known is True
    assert norm_ptx.snomed_id == "SNOMED:36118008"
    assert norm_ptx.organ_system == "Respiratory"

    # 4. Spondylolisthesis
    norm_spond = normalizer.normalize("spondylolisthesis")
    assert norm_spond.is_known is True
    assert norm_spond.snomed_id == "SNOMED:274152003"
    assert norm_spond.organ_system == "Musculoskeletal"


def test_normalizer_abbreviation_and_cache_composition():
    normalizer = TerminologyNormalizer(online=False)

    # Raw abbreviation MPD
    norm = normalizer.normalize("MPD")
    assert norm.is_known is True
    assert "pancreatic" in norm.preferred_term.lower()


def test_normalizer_unknown_concept_isolation():
    normalizer = TerminologyNormalizer(online=False)

    # Non-medical text / hallucinated noise
    norm_unknown = normalizer.normalize("non_existent_clinical_finding_xyz_12345")
    assert norm_unknown.is_known is False
    assert norm_unknown.snomed_id is None
    assert norm_unknown.layman_synonym is None
    assert norm_unknown.source == "unmapped"


def test_terminology_client_infer_organ_system():
    client = TerminologyClient()
    assert client._infer_organ_system("Aortic Valve Regurgitation") == "Cardiovascular"
    assert client._infer_organ_system("Right Lower Lobe Consolidation") == "Respiratory"
    assert client._infer_organ_system("Cholelithiasis with Gallstones") == "Gastrointestinal"
    assert client._infer_organ_system("Lumbar Disc Bulge") == "Musculoskeletal"
    assert client._infer_organ_system("Renal Calculi") == "Genitourinary"
    assert client._infer_organ_system("Cerebral Infarction") == "Neurological"


def test_dynamic_learning_and_caching(tmp_path):
    # Use temporary cache file to test write-through persistence
    temp_cache_file = str(tmp_path / "test_cache.json")

    class MockClient(TerminologyClient):
        def search_snomed(self, query):
            if query.lower() == "nephrolithiasis":
                return {
                    "snomed_id": "SNOMED:95570007",
                    "preferred_term": "Nephrolithiasis",
                    "layman_synonym": "Kidney stones",
                    "organ_system": "Genitourinary",
                    "source": "ols_snomed",
                }
            return None

    normalizer = TerminologyNormalizer(
        cache_path=temp_cache_file,
        online=True,
        client=MockClient(),
    )

    # 1. First lookup: not in local cache -> triggers client lookup -> saves to cache
    res = normalizer.normalize("nephrolithiasis")
    assert res.is_known is True
    assert res.snomed_id == "SNOMED:95570007"
    assert res.layman_synonym == "Kidney stones"

    # 2. Verify it was written to disk
    assert os.path.exists(temp_cache_file)

    # 3. Create a brand new offline normalizer reading that file -> must resolve offline!
    offline_normalizer = TerminologyNormalizer(
        cache_path=temp_cache_file,
        online=False,
    )
    res_offline = offline_normalizer.normalize("nephrolithiasis")
    assert res_offline.is_known is True
    assert res_offline.snomed_id == "SNOMED:95570007"
    assert res_offline.source == "local_cache"
