"""
clinical_extraction/report_rules/base.py

Base class for report-type specific extraction rules.

Defines the interface and common helper methods for entity, finding,
and anatomy extraction across all clinical document categories.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from clinical_extraction.entities import (
    create_anatomy,
    create_entity,
    create_finding,
)
from clinical_extraction.filters import (
    filter_measurements,
    is_explanatory_section,
    is_valid_finding_text,
)
from clinical_extraction.models import (
    AnatomicalEntity,
    AssertionStatus,
    ClinicalEntity,
    ClinicalFinding,
    ClinicalMeasurement,
    EntityType,
)
from clinical_extraction.negation import detect_assertion, split_into_clauses
from clinical_extraction.normalization import normalize_term


class BaseReportRules:
    """Base class for all report-type extraction rule sets."""

    report_type: str = "generic"

    # Subclasses define these sets of terms/patterns
    ANATOMY_PATTERNS: list[str] = []
    FINDING_PATTERNS: list[str] = []

    def extract_anatomy(
        self,
        sections: list[Any],
    ) -> list[AnatomicalEntity]:
        """Extract explicit anatomical mentions from document sections."""
        anatomy: list[AnatomicalEntity] = []
        seen: set[tuple[str, Optional[int]]] = set()

        for sec in sections:
            sec_text = getattr(sec, "text", "") or ""
            sec_title = getattr(sec, "title", None)
            sec_page = getattr(sec, "page", None)

            full_text = f"{sec_title or ''} {sec_text}"

            for pat in self.ANATOMY_PATTERNS:
                # Word boundary match
                regex = re.compile(rf"\b{re.escape(pat)}\b", re.IGNORECASE)
                for match in regex.finditer(full_text):
                    term = match.group(0)
                    key = (term.lower(), sec_page)
                    if key in seen:
                        continue

                    # Trace verbatim sentence or context
                    start = max(0, match.start() - 30)
                    end = min(len(full_text), match.end() + 30)
                    context_snippet = full_text[start:end].strip()

                    norm = normalize_term(term, self.report_type)
                    anatomy.append(
                        create_anatomy(
                            text=term,
                            normalized=norm,
                            page=sec_page,
                            source_section=sec_title,
                            source_text=context_snippet,
                        )
                    )
                    seen.add(key)

        return anatomy

    def extract_findings(
        self,
        sections: list[Any],
    ) -> list[ClinicalFinding]:
        """Extract clinical observations and findings with assertion status."""
        findings: list[ClinicalFinding] = []
        seen: set[tuple[str, Optional[int]]] = set()

        for sec in sections:
            sec_text = getattr(sec, "text", "") or ""
            sec_title = getattr(sec, "title", None)
            sec_page = getattr(sec, "page", None)

            if not sec_text:
                continue

            # Skip sections that contain explanatory/educational prose only
            # (e.g. "Interpretation", "Comment", "Remarks", "Increased in")
            if is_explanatory_section(sec_title):
                continue

            clauses = split_into_clauses(sec_text)
            for clause in clauses:
                clause_clean = clause.strip()
                if not clause_clean or len(clause_clean) < 2:
                    continue

                for pat in self.FINDING_PATTERNS:
                    regex = re.compile(rf"\b{re.escape(pat)}\b", re.IGNORECASE)
                    match = regex.search(clause_clean)
                    if match:
                        # Gate: reject multi-sentence paragraphs / very long text
                        if not is_valid_finding_text(clause_clean):
                            break
                        assertion, is_negated = detect_assertion(clause_clean, pat)
                        norm = normalize_term(clause_clean, self.report_type)
                        if not norm:
                            norm = normalize_term(pat, self.report_type)

                        key = (clause_clean.lower(), sec_page)
                        if key not in seen:
                            findings.append(
                                create_finding(
                                    text=clause_clean,
                                    normalized=norm,
                                    assertion=assertion,
                                    negated=is_negated,
                                    page=sec_page,
                                    source_section=sec_title,
                                    source_text=clause_clean,
                                )
                            )
                            seen.add(key)
                        break  # Only one primary finding per clause to avoid overlap

        return findings

    def extract_entities(
        self,
        sections: list[Any],
        findings: list[ClinicalFinding],
        anatomy: list[AnatomicalEntity],
    ) -> list[ClinicalEntity]:
        """Assemble all extracted clinical entities."""
        entities: list[ClinicalEntity] = []
        seen: set[tuple[str, str, Optional[int]]] = set()

        # Add findings as ClinicalEntity
        for f in findings:
            key = (f.text.lower(), EntityType.FINDING, f.page)
            if key not in seen:
                entities.append(
                    create_entity(
                        text=f.text,
                        entity_type=EntityType.FINDING,
                        normalized=f.normalized,
                        assertion=f.assertion,
                        negated=f.negated,
                        page=f.page,
                        source_section=f.source_section,
                        source_text=f.source_text,
                    )
                )
                seen.add(key)

        # Add anatomy as ClinicalEntity
        for a in anatomy:
            key = (a.text.lower(), EntityType.ANATOMY, a.page)
            if key not in seen:
                entities.append(
                    create_entity(
                        text=a.text,
                        entity_type=EntityType.ANATOMY,
                        normalized=a.normalized,
                        assertion=AssertionStatus.PRESENT,
                        negated=False,
                        page=a.page,
                        source_section=a.source_section,
                        source_text=a.source_text,
                    )
                )
                seen.add(key)

        return entities

    def extract_measurements(
        self,
        sections: list[Any],
        phase1_measurements: Optional[list[Any]] = None,
    ) -> list[ClinicalMeasurement]:
        """Extract measurements from document sections and existing Phase 1 measurements."""
        from clinical_extraction.measurements import extract_measurements
        return extract_measurements(
            phase1_measurements=phase1_measurements or [],
            sections=sections,
            report_type=self.report_type,
        )
