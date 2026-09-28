"""
Hybrid Clinical Fact Extractor.
Combines Phase 3 deterministic measurement grammar with Phase 4 concept extraction
and strict text-grounding validation.
"""

from typing import List, Optional
from src.segmentation.models import Clause
from src.extraction.rules.models import ExtractedFact
from src.extraction.rules.measurements import MeasurementParser
from src.extraction.rules.assertions import AssertionClassifier
from src.extraction.rules.rule_extractor import RuleExtractor
from src.extraction.model.concept_extractor import ConceptExtractor
from src.extraction.model.grounding import GroundingValidator


class HybridClinicalExtractor:
    """
    Complete hybrid extractor:
    - Numbers, ranges, units: 100% deterministic regex grammars.
    - Concept names: Grounded concept extractor with strict text validation.
    - Assertions: Checked via deterministic trigger rules.
    """

    def __init__(self, concept_extractor: Optional[ConceptExtractor] = None):
        self.concept_extractor = concept_extractor or ConceptExtractor()

    def extract_from_clause(self, clause: Clause) -> List[ExtractedFact]:
        text = clause.text.strip()
        facts: List[ExtractedFact] = []

        # 1. If clause has explicit numbers or reference ranges, use Phase 3 rules
        has_number = any(char.isdigit() for char in text)
        if has_number or clause.is_table_row:
            rule_facts = RuleExtractor.extract_from_clause(clause)
            if rule_facts:
                return rule_facts

        # 2. Extract concepts using ConceptExtractor
        items = self.concept_extractor.extract_concepts(text)
        # 3. Grounding check
        grounded_items = GroundingValidator.filter_items(items, text)

        for idx, item in enumerate(grounded_items):
            c_name = item.get("concept", "").strip()
            # Double check assertion with rule classifier
            assertion = item.get("assertion", "").upper()
            if assertion not in {"PRESENT", "ABSENT", "NORMAL"}:
                assertion = AssertionClassifier.classify(text)

            facts.append(ExtractedFact(
                fact_id=f"{clause.clause_id}:m{idx+1}",
                concept=c_name,
                assertion=assertion,
                measurement=None,
                source_text=text,
                clause_id=clause.clause_id,
                page_number=clause.page_number,
                section_name=clause.section_name
            ))

        return facts

    def extract_from_clauses(self, clauses: List[Clause]) -> List[ExtractedFact]:
        all_facts: List[ExtractedFact] = []
        for c in clauses:
            all_facts.extend(self.extract_from_clause(c))
        return all_facts
