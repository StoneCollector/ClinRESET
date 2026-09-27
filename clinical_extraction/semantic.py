"""
clinical_extraction/semantic.py

Controlled semantic structuring layer for Phase 4.

Assigns standardized clinical semantic categories, extracts linguistic modifiers
(e.g., severity text, grading, pattern) without clinical interpretation or risk
judgment, and establishes structured connections to related anatomy.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from clinical_extraction.models import (
    AnatomicalEntity,
    ClinicalEntity,
    ClinicalFinding,
    ClinicalMeasurement,
    ClinicalRelationship,
    EntityType,
    SemanticCategory,
)

# Standardized canonical anatomy names
ANATOMY_CANONICAL_NAMES: dict[str, str] = {
    "left ventricle": "Left Ventricle",
    "right ventricle": "Right Ventricle",
    "left atrium": "Left Atrium",
    "right atrium": "Right Atrium",
    "aortic root": "Aortic Root",
    "aortic valve": "Aortic Valve",
    "mitral valve": "Mitral Valve",
    "tricuspid valve": "Tricuspid Valve",
    "pulmonary valve": "Pulmonary Valve",
    "pulmonic valve": "Pulmonary Valve",
    "pericardium": "Pericardium",
    "pulmonary artery": "Pulmonary Artery",
    "aorta": "Aorta",
    "interatrial septum": "Interatrial Septum",
    "interventricular septum": "Interventricular Septum",
    "left ventricular outflow tract": "Left Ventricular Outflow Tract",
    "lvot": "Left Ventricular Outflow Tract",
    "rvot": "Right Ventricular Outflow Tract",
}

# Modifiers patterns (linguistic extraction only — NOT clinical risk judgment)
SEVERITY_PATTERN = re.compile(r"\b(mild|moderate|severe|trace|trivial)\b", re.IGNORECASE)
GRADE_PATTERN = re.compile(r"\b(grade\s*(?:[1-4]|i{1,3}|iv))\b", re.IGNORECASE)
PATTERN_PATTERN = re.compile(r"\b(concentric|eccentric|conc)\b", re.IGNORECASE)


def extract_linguistic_modifiers(text: str) -> dict[str, Any]:
    """
    Extract linguistic qualifiers directly from source surface text.

    Preserves the verbatim source wording (e.g. "Mild", "Grade 1", "Concentric").
    Strictly forbidden to infer prognosis, risk, or clinical concern.
    """
    modifiers: dict[str, Any] = {}
    if not text:
        return modifiers

    # Severity qualifier
    sev_match = SEVERITY_PATTERN.search(text)
    if sev_match:
        modifiers["severity_text"] = sev_match.group(1).capitalize()

    # Grading qualifier
    grade_match = GRADE_PATTERN.search(text)
    if grade_match:
        raw_grade = grade_match.group(1)
        # Normalize Roman to Arabic if needed, e.g. "grade i" -> "Grade 1"
        cleaned_grade = re.sub(r"\s+", " ", raw_grade).title()
        cleaned_grade = re.sub(r"\bIii\b", "3", cleaned_grade)
        cleaned_grade = re.sub(r"\bIi\b", "2", cleaned_grade)
        cleaned_grade = re.sub(r"\bI\b", "1", cleaned_grade)
        cleaned_grade = re.sub(r"\bIv\b", "4", cleaned_grade)
        modifiers["grade_text"] = cleaned_grade

    # Pattern qualifier
    pat_match = PATTERN_PATTERN.search(text)
    if pat_match:
        raw_pat = pat_match.group(1).lower()
        if raw_pat in ("conc", "concentric"):
            modifiers["pattern"] = "Concentric"
        elif raw_pat == "eccentric":
            modifiers["pattern"] = "Eccentric"

    return modifiers


def determine_finding_semantic_category(text: str, normalized: Optional[str] = None) -> str:
    """
    Determine the controlled semantic category for a clinical finding.

    Parameters
    ----------
    text:
        Surface text of the finding.
    normalized:
        Normalized clinical term if resolved.

    Returns
    -------
    str:
        Controlled category from SemanticCategory.
    """
    target = f"{normalized or ''} {text}".lower()

    # Wall motion
    if any(k in target for k in ("rwma", "wall motion", "hypokines", "akines", "dyskines")):
        return SemanticCategory.WALL_MOTION

    # Diastolic function
    if any(k in target for k in ("lvdd", "diastolic dysfunction", "diastolic function", "e/a", "e/e'")):
        return SemanticCategory.DIASTOLIC_FUNCTION

    # Valvular finding (regurgitation, stenosis, leaflet motion, valve waveforms)
    if any(
        k in target
        for k in (
            "regurgitation",
            "stenosis",
            "prolapse",
            "valve",
            "leaflet",
            "opens well",
            "ef slope",
            "a wave",
            "midsystolic notch",
            "mild tr",
            "moderate tr",
            "severe tr",
            "mild mr",
            "moderate mr",
            "severe mr",
            "mild ar",
            "moderate ar",
            "severe ar",
            "mild pr",
        )
    ):
        return SemanticCategory.VALVULAR_FINDING

    # Effusion
    if "effusion" in target:
        return SemanticCategory.EFFUSION

    # Thrombus
    if any(k in target for k in ("thrombus", "clot")):
        return SemanticCategory.THROMBUS

    # Structural findings (hypertrophy, septal integrity, vegetation, mass)
    if any(
        k in target
        for k in (
            "lvh",
            "hypertrophy",
            "intact",
            "septum",
            "septa",
            "vegetation",
            "mass",
            "defect",
            "aneurysm",
        )
    ):
        return SemanticCategory.STRUCTURAL_FINDING

    # Function findings (overall chamber function)
    if any(k in target for k in ("lv function", "rv function", "systolic function", "cardiac function")):
        return SemanticCategory.FUNCTION

    # Doppler / Pressure measurements expressed as findings
    if any(k in target for k in ("gradient", "velocity", "flow")):
        return SemanticCategory.DOPPLER_MEASUREMENT

    return SemanticCategory.OTHER_CLINICAL


def determine_measurement_semantic_category(name: str, normalized_name: Optional[str] = None) -> str:
    """
    Determine the controlled semantic category for a measurement.

    Parameters
    ----------
    name:
        Measurement parameter name.
    normalized_name:
        Normalized parameter name.

    Returns
    -------
    str:
        Controlled category from SemanticCategory.
    """
    target = f"{normalized_name or ''} {name}".lower()

    if any(k in target for k in ("ejection fraction", "fractional shortening")):
        return SemanticCategory.FUNCTION

    if any(k in target for k in ("pasp", "systolic pressure", "pressure")):
        return SemanticCategory.PRESSURE

    if any(k in target for k in ("velocity", "gradient", "doppler")):
        return SemanticCategory.DOPPLER_MEASUREMENT

    return SemanticCategory.MEASUREMENT


def canonicalize_anatomy_name(target: str) -> str:
    """Map anatomy term to standard Title Case canonical name."""
    clean = target.strip().lower()
    return ANATOMY_CANONICAL_NAMES.get(clean, clean.title())


def assign_semantic_metadata(
    findings: list[ClinicalFinding],
    measurements: list[ClinicalMeasurement],
    entities: list[ClinicalEntity],
    anatomy: list[AnatomicalEntity],
    relationships: list[ClinicalRelationship],
    report_type: Optional[str] = None,
) -> None:
    """
    Enrich all extracted clinical items with semantic categories, linguistic
    modifiers, and standardized related anatomy references in-place.
    """
    # Build fast lookup for relationships by source item text
    rel_targets_by_source: dict[str, list[str]] = {}
    for r in relationships:
        canon_target = canonicalize_anatomy_name(r.target)
        rel_targets_by_source.setdefault(r.source, []).append(canon_target)

    # 1. Findings
    for f in findings:
        f.semantic_category = determine_finding_semantic_category(f.text, f.normalized)
        f.modifiers = extract_linguistic_modifiers(f.text)

        # Related anatomy from relationships
        related = list(rel_targets_by_source.get(f.text, []))

        # Check if concept or text explicitly contains a known anatomical structure
        search_target = f"{f.normalized or ''} {f.text}".lower()
        for anat_key, canon_name in ANATOMY_CANONICAL_NAMES.items():
            # Match multi-word anatomy or word-bounded terms
            if len(anat_key) > 3 and anat_key in search_target:
                if canon_name not in related:
                    related.append(canon_name)

        # Explicit multi-target fallback if not already captured
        f_lower = f.text.lower()
        if "la/lv" in f_lower or ("la" in f_lower and "lv" in f_lower and "clot" in f_lower):
            for t in ("Left Atrium", "Left Ventricle"):
                if t not in related:
                    related.append(t)
        if "ias" in f_lower and "ivs" in f_lower:
            for t in ("Interatrial Septum", "Interventricular Septum"):
                if t not in related:
                    related.append(t)

        f.related_anatomy = related

    # 2. Measurements
    for m in measurements:
        m.semantic_category = determine_measurement_semantic_category(m.name, m.normalized_name)
        m.modifiers = extract_linguistic_modifiers(m.name)
        m.related_anatomy = list(rel_targets_by_source.get(m.name, []))

    # 3. Anatomy entities
    for a in anatomy:
        a.semantic_category = SemanticCategory.ANATOMY
        a.modifiers = {}

    # 4. Entities (enrich findings/measurements/anatomy consistently)
    for e in entities:
        if e.type == EntityType.ANATOMY:
            e.semantic_category = SemanticCategory.ANATOMY
            e.modifiers = {}
            e.related_anatomy = [canonicalize_anatomy_name(e.normalized or e.text)]
        elif e.type == EntityType.MEASUREMENT:
            e.semantic_category = determine_measurement_semantic_category(e.text, e.normalized)
            e.modifiers = extract_linguistic_modifiers(e.text)
            e.related_anatomy = list(rel_targets_by_source.get(e.text, []))
        else:
            e.semantic_category = determine_finding_semantic_category(e.text, e.normalized)
            e.modifiers = extract_linguistic_modifiers(e.text)
            e.related_anatomy = list(rel_targets_by_source.get(e.text, []))
