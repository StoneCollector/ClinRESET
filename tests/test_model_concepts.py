import pytest
from src.extraction.model.grounding import GroundingValidator
from src.extraction.model.concept_extractor import ConceptExtractor

# Exact 16 held-out benchmark test cases from clause_extraction_model_test.ipynb
TESTS = [
    ("No focal lesion is seen.", [("focal lesion", "ABSENT")]),
    ("No disc bulge is noted.", [("disc bulge", "ABSENT")]),
    ("MPD is not dilated.", [("mpd", "ABSENT")]),
    ("No e/o any calculus / mass seen in its lumen.", [("calculus", "ABSENT"), ("mass", "ABSENT")]),
    ("No subluxation / dislocation / spondylolisthesis is seen.", [("subluxation", "ABSENT"), ("dislocation", "ABSENT"), ("spondylolisthesis", "ABSENT")]),
    ("Mild acne on face, no hirsutism.", [("acne", "PRESENT"), ("hirsutism", "ABSENT")]),
    ("Large right sided pneumothorax is seen with mild pleural effusion.", [("pneumothorax", "PRESENT"), ("effusion", "PRESENT")]),
    ("Lung feilds are clear.", [("lung", "NORMAL")]),
    ("Hila appear normal", [("hila", "NORMAL")]),
    ("The facet joints are unremarkable.", [("facet", "NORMAL")]),
    ("Cardio-thoracic ratio is within normal limits.", [("cardio", "NORMAL")]),
    ("Loss of lumbar lordosis.", [("lordosis", "PRESENT")]),
    ("Liver is enlarged in size (~15.8cm), normal in outline.", [("liver", "PRESENT")]),
    ("IVD Spaces are normal", [("ivd", "NORMAL")]),
    ("Grade 1 left ventricular diastolic dysfunction.", [("diastolic", "PRESENT")]),
    ("Two small echogenic calculi measuring ~4mm are seen in lower calyx.", [("calcul", "PRESENT")]),
]


def test_grounding_validator():
    sentence = "No pericardial effusion is seen."

    # Grounded concept
    assert GroundingValidator.is_grounded("pericardial effusion", sentence) is True
    assert GroundingValidator.is_grounded("effusion", sentence) is True

    # Hallucinated concepts
    assert GroundingValidator.is_grounded("pancreatic adenocarcinoma", sentence) is False
    assert GroundingValidator.is_grounded("intracranial hemorrhage", sentence) is False
    assert GroundingValidator.is_grounded("myocardial infarction", sentence) is False


def test_concept_extraction_held_out_benchmark():
    """
    CRITICAL PHASE 4 CRITERION:
    >= 90% recall and assertion on held-out clauses from clause_extraction_model_test.ipynb.
    """
    extractor = ConceptExtractor()

    n_gold = sum(len(g) for _, g in TESTS)
    found = 0
    correct = 0
    ungrounded = 0

    print("\n--- Evaluating Held-Out Benchmark Clauses ---")
    for sentence, gold in TESTS:
        items = extractor.extract_concepts(sentence)
        assert items is not None

        # Check for ungrounded items
        for item in items:
            concept = item.get("concept", "")
            if not GroundingValidator.is_grounded(concept, sentence):
                ungrounded += 1

        # Check recall and assertion matches
        for kw, expected_assertion in gold:
            matches = [x for x in items if kw.lower() in str(x.get("concept", "")).lower()]
            if matches:
                found += 1
                if any(str(x.get("assertion", "")).upper() == expected_assertion for x in matches):
                    correct += 1
            else:
                print(f"MISSED: '{kw}' in '{sentence}' -> Extracted: {items}")

    recall_pct = (found / n_gold) * 100.0
    assertion_pct = (correct / n_gold) * 100.0

    print(f"\nTotal Gold Targets: {n_gold}")
    print(f"Concept Recall: {found}/{n_gold} ({recall_pct:.1f}%)")
    print(f"Assertion Correctness: {correct}/{n_gold} ({assertion_pct:.1f}%)")
    print(f"Ungrounded Hallucinations: {ungrounded}")

    # Phase 4 Success Criteria: >= 90% recall and assertion accuracy
    assert recall_pct >= 90.0, f"Expected >=90% recall, got {recall_pct:.1f}%"
    assert assertion_pct >= 90.0, f"Expected >=90% assertion accuracy, got {assertion_pct:.1f}%"
    assert ungrounded == 0, f"Expected 0 ungrounded items, got {ungrounded}"
