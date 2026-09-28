"""
Rule-Based Clinical Fact Extractor (No Model).
Extracts measurements, ranges, and assertions deterministically from clinical clauses.
"""

import re
from typing import List, Optional
from src.segmentation.models import Clause
from .models import ExtractedFact, Measurement
from .measurements import MeasurementParser
from .assertions import AssertionClassifier


class RuleExtractor:
    """Extracts grounded clinical facts using deterministic regex grammars and rules."""

    @classmethod
    def extract_from_clause(cls, clause: Clause) -> List[ExtractedFact]:
        facts: List[ExtractedFact] = []
        text = clause.text.strip()
        f_idx = 0

        # 1. Check for Blood Pressure
        bp_result = MeasurementParser.parse_blood_pressure(text)
        if bp_result:
            m_sys, m_dia = bp_result
            f_idx += 1
            facts.append(ExtractedFact(
                fact_id=f"{clause.clause_id}:f{f_idx}",
                concept="systolic blood pressure",
                assertion="NORMAL" if m_sys.value <= 130 else "PRESENT",
                measurement=m_sys,
                source_text=text,
                clause_id=clause.clause_id,
                page_number=clause.page_number,
                section_name=clause.section_name
            ))
            f_idx += 1
            facts.append(ExtractedFact(
                fact_id=f"{clause.clause_id}:f{f_idx}",
                concept="diastolic blood pressure",
                assertion="NORMAL" if m_dia.value <= 85 else "PRESENT",
                measurement=m_dia,
                source_text=text,
                clause_id=clause.clause_id,
                page_number=clause.page_number,
                section_name=clause.section_name
            ))
            return facts

        # 2. Check for Table / In-Situ Range Measurement
        range_result = MeasurementParser.parse_in_situ_range_measurement(text)
        if range_result:
            concept_prefix, meas = range_result
            concept = cls._clean_concept(concept_prefix) or "measurement"

            # Determine assertion from in-situ reference range
            assertion = "NORMAL"
            if meas.reference_range and meas.reference_range.low is not None and meas.reference_range.high is not None:
                if meas.value < meas.reference_range.low or meas.value > meas.reference_range.high:
                    assertion = "PRESENT"

            f_idx += 1
            facts.append(ExtractedFact(
                fact_id=f"{clause.clause_id}:f{f_idx}",
                concept=concept,
                assertion=assertion,
                measurement=meas,
                source_text=text,
                clause_id=clause.clause_id,
                page_number=clause.page_number,
                section_name=clause.section_name
            ))
            return facts

        # 3. Check for Key-Value / Inline Measurement
        kv_result = MeasurementParser.parse_key_value_measurement(text)
        if kv_result:
            concept_prefix, meas = kv_result
            concept = cls._clean_concept(concept_prefix) or "finding measurement"
            assertion = AssertionClassifier.classify(text)

            f_idx += 1
            facts.append(ExtractedFact(
                fact_id=f"{clause.clause_id}:f{f_idx}",
                concept=concept,
                assertion=assertion,
                measurement=meas,
                source_text=text,
                clause_id=clause.clause_id,
                page_number=clause.page_number,
                section_name=clause.section_name
            ))
            return facts

        # 4. Narrative Non-Measurement Clinical Statement
        assertion = AssertionClassifier.classify(text)
        concept = cls._extract_narrative_concept(text, assertion)

        if concept and len(concept) >= 2:
            f_idx += 1
            facts.append(ExtractedFact(
                fact_id=f"{clause.clause_id}:f{f_idx}",
                concept=concept,
                assertion=assertion,
                measurement=None,
                source_text=text,
                clause_id=clause.clause_id,
                page_number=clause.page_number,
                section_name=clause.section_name
            ))

        return facts

    @classmethod
    def extract_from_clauses(cls, clauses: List[Clause]) -> List[ExtractedFact]:
        all_facts: List[ExtractedFact] = []
        for c in clauses:
            all_facts.extend(cls.extract_from_clause(c))
        return all_facts

    @classmethod
    def _extract_narrative_concept(cls, text: str, assertion: str) -> str:
        """Extracts the central clinical concept from a narrative clause."""
        clean = text.strip()

        # Remove leading assertion cue markers
        clean = re.sub(
            r"^(?:no\s+evidence\s+of(?:\s+any)?|no\s+e/o(?:\s+any)?|no\s+sign\s+of|negative\s+for|without|no|not|mild|moderate|severe|grade\s+[0-9IViv]+)\s+",
            "", clean, flags=re.IGNORECASE
        )

        # Remove trailing status suffixes
        clean = re.sub(
            r"\s+(?:is\s+seen|are\s+seen|seen|noted|detected|identified|present|normal|intact|clear|unremarkable|appears?\s+normal|within\s+normal\s+limits|wnl|opening\s+well|opens\s+well)\.?$",
            "", clean, flags=re.IGNORECASE
        )

        # Remove colon prefixes (e.g. "Liver: normal in outline" -> "outline" or "liver")
        if ":" in clean:
            parts = clean.split(":", 1)
            prefix = parts[0].strip()
            suffix = parts[1].strip()
            if assertion == "NORMAL" and ("normal" in suffix.lower() or "intact" in suffix.lower() or not suffix):
                clean = prefix
            elif suffix:
                clean = f"{prefix} {suffix}"

        return cls._clean_concept(clean)

    @classmethod
    def _clean_concept(cls, concept: str) -> str:
        clean = re.sub(r"^[ \t:.-]+|[ \t:.-]+$", "", concept)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
