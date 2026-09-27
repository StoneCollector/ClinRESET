"""
clinical_extraction/extractor.py

Main orchestrator for Phase 3: Clinical Information Extraction.

Extracts structured clinical facts from the classified report:
- Reuses Phase 1 measurements and extracts inline narrative measurements.
- Extracts explicit clinical findings and observations.
- Detects negation and assigns assertion status.
- Extracts anatomical structures.
- Establishes traceable relationships without speculation.
- Applies terminology normalization while preserving original source text.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from clinical_extraction.entities import create_entity
from clinical_extraction.measurements import extract_measurements
from clinical_extraction.models import (
    AssertionStatus,
    ClinicalEntity,
    ClinicalInformation,
    EntityType,
)
from clinical_extraction.relations import extract_relationships
from clinical_extraction.report_rules import get_rules_for_report_type


logger = logging.getLogger("clinical_extraction.extractor")


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve attribute from dataclass/object or key from dictionary."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def extract_clinical_info(result: Any) -> ClinicalInformation:
    """
    Transform a classified report into structured clinical information.

    Accepts either an ExtractionResult dataclass instance or a report.json dict.

    Parameters
    ----------
    result:
        ExtractionResult from Phase 1/Phase 2 or a parsed report.json dictionary.

    Returns
    -------
    ClinicalInformation
        Structured clinical facts with complete provenance.
    """
    # 1. Determine classified report type context
    report_type: Optional[str] = None
    classification = _get_field(result, "classification", None)

    if classification:
        if isinstance(classification, dict):
            report_type = classification.get("report_type")
        else:
            report_type = getattr(classification, "report_type", None)

    logger.info("Extracting clinical information (report_type=%s)", report_type)

    # 2. Select rule engine
    rules = get_rules_for_report_type(report_type)

    # 3. Extract inputs from result
    sections = _get_field(result, "sections", []) or []
    tables = _get_field(result, "tables", []) or []
    phase1_measurements = _get_field(result, "measurements", []) or []

    # If measurements are dicts, convert temporarily to simple namespace for measurements module
    normalized_meas_inputs = []
    for m in phase1_measurements:
        if isinstance(m, dict):
            class _SimpleMeas:
                def __init__(self, d: dict):
                    self.name = d.get("name")
                    self.value = d.get("value")
                    self.unit = d.get("unit")
                    self.reference_range = d.get("reference_range")
                    self.page = d.get("page")
                    self.source_section = d.get("source_section")
            normalized_meas_inputs.append(_SimpleMeas(m))
        else:
            normalized_meas_inputs.append(m)

    # If sections are dicts, convert temporarily
    normalized_sec_inputs = []
    for s in sections:
        if isinstance(s, dict):
            class _SimpleSec:
                def __init__(self, d: dict):
                    self.title = d.get("title")
                    self.text = d.get("text", "")
                    self.page = d.get("page")
            normalized_sec_inputs.append(_SimpleSec(s))
        else:
            normalized_sec_inputs.append(s)

    # 4. Extract Measurements (reuses Phase 1 + narrative inline)
    measurements = extract_measurements(
        normalized_meas_inputs,
        normalized_sec_inputs,
        report_type=report_type,
    )

    # 5. Extract Anatomy
    anatomy = rules.extract_anatomy(normalized_sec_inputs)

    # 6. Extract Findings
    findings = rules.extract_findings(normalized_sec_inputs)

    # 7. Assemble Entities (findings + anatomy + measurements)
    entities = rules.extract_entities(normalized_sec_inputs, findings, anatomy)

    # Add measurements to entities list as MEASUREMENT type
    seen_entity_keys = {(e.text.lower(), e.type, e.page) for e in entities}
    for m in measurements:
        key = (m.name.lower(), EntityType.MEASUREMENT, m.page)
        if key not in seen_entity_keys:
            entities.append(
                create_entity(
                    text=m.name,
                    entity_type=EntityType.MEASUREMENT,
                    normalized=m.normalized_name,
                    assertion=AssertionStatus.PRESENT,
                    negated=False,
                    page=m.page,
                    source_section=m.source_section,
                    source_text=m.source_text,
                )
            )
            seen_entity_keys.add(key)

    # 8. Extract Relationships
    relationships = extract_relationships(
        findings=findings,
        measurements=measurements,
        anatomy=anatomy,
        report_type=report_type,
    )

    logger.info(
        "Extraction summary: %d entities, %d measurements, %d findings, %d anatomy, %d relationships",
        len(entities),
        len(measurements),
        len(findings),
        len(anatomy),
        len(relationships),
    )

    return ClinicalInformation(
        entities=entities,
        measurements=measurements,
        findings=findings,
        anatomy=anatomy,
        relationships=relationships,
    )
