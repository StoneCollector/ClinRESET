"""
clinical_extraction/relations.py

Clinical relationship extraction layer.

Connects findings and measurements to their explicit anatomical sites
or related clinical parameters without speculative inference.
"""

from __future__ import annotations

import re
from typing import Optional

from clinical_extraction.models import (
    AnatomicalEntity,
    ClinicalFinding,
    ClinicalMeasurement,
    ClinicalRelationship,
    RelationType,
)


# Domain-specific mapping from finding/measurement keywords to anatomical targets
ECHO_ANATOMY_MAPPINGS: dict[str, str] = {
    "lvh": "left ventricle",
    "conc lvh": "left ventricle",
    "concentric lvh": "left ventricle",
    "rwma": "left ventricle",
    "no rwma": "left ventricle",
    "lvdd": "left ventricle",
    "grade 1 lvdd": "left ventricle",
    "lv function": "left ventricle",
    "normal lv function": "left ventricle",
    "rv function": "right ventricle",
    "normal rv function": "right ventricle",
    "tr": "tricuspid valve",
    "mild tr": "tricuspid valve",
    "tricuspid regurgitation": "tricuspid valve",
    "mr": "mitral valve",
    "mitral regurgitation": "mitral valve",
    "ar": "aortic valve",
    "aortic regurgitation": "aortic valve",
    "no aortic regurgitation": "aortic valve",
    "pr": "pulmonary valve",
    "pulmonary regurgitation": "pulmonary valve",
    "no pulmonary regurgitation": "pulmonary valve",
    "no pulmonary regurgitation present": "pulmonary valve",
    "effusion": "pericardium",
    "no effusion": "pericardium",
    "pericardial effusion": "pericardium",
    "ejection fraction": "left ventricle",
    "fractional shortening": "left ventricle",
    "aortic root diameter": "aortic root",
    "aortic root": "aortic root",
    "left atrial diameter": "left atrium",
    "left ventricular ed dimension": "left ventricle",
    "left ventricular es dimension": "left ventricle",
    "inter vent. septum thickness d": "interventricular septum",
    "lvposterior wall thickness d": "left ventricle",
    "pasp": "pulmonary artery",
    "aortic velocity": "aorta",
    "pulmonary velocity": "pulmonary artery",
    "no gradient across lvot": "LVOT",
}


def extract_relationships(
    findings: list[ClinicalFinding],
    measurements: list[ClinicalMeasurement],
    anatomy: list[AnatomicalEntity],
    report_type: Optional[str] = None,
) -> list[ClinicalRelationship]:
    """
    Extract traceable relationships connecting findings and measurements
    to anatomical structures and parameters.

    Parameters
    ----------
    findings:
        Extracted clinical findings.
    measurements:
        Extracted measurements.
    anatomy:
        Extracted anatomical structures.
    report_type:
        Contextual report type.

    Returns
    -------
    list[ClinicalRelationship]
        Relationships established by direct evidence.
    """
    relationships: list[ClinicalRelationship] = []
    seen: set[tuple[str, str, str]] = set()

    # 1. Co-occurrence / Syntactic matching in findings
    for f in findings:
        f_text_clean = f.text.strip().lower()
        f_src = f.source_text or f.text

        # Check explicit domain mappings
        target_anatomy = ECHO_ANATOMY_MAPPINGS.get(f_text_clean)
        if not target_anatomy:
            # Check if any mapping key is substring of finding
            for k, anat in ECHO_ANATOMY_MAPPINGS.items():
                if re.search(rf"\b{re.escape(k)}\b", f_text_clean):
                    target_anatomy = anat
                    break

        if target_anatomy:
            key = (f.text, RelationType.ASSOCIATED_WITH, target_anatomy)
            if key not in seen:
                relationships.append(
                    ClinicalRelationship(
                        source=f.text,
                        relation=RelationType.ASSOCIATED_WITH,
                        target=target_anatomy,
                        page=f.page,
                        source_text=f_src,
                    )
                )
                seen.add(key)

        # Multi-target cases: e.g. "No LA/LV clot" -> target: left atrium and left ventricle
        if "la/lv" in f_text_clean or ("la" in f_text_clean and "lv" in f_text_clean):
            for t in ("left atrium", "left ventricle"):
                key = (f.text, RelationType.ASSOCIATED_WITH, t)
                if key not in seen:
                    relationships.append(
                        ClinicalRelationship(
                            source=f.text,
                            relation=RelationType.ASSOCIATED_WITH,
                            target=t,
                            page=f.page,
                            source_text=f_src,
                        )
                    )
                    seen.add(key)

        # "IAS/IVS intact" -> interatrial septum and interventricular septum
        if "ias" in f_text_clean and "ivs" in f_text_clean:
            for t in ("interatrial septum", "interventricular septum"):
                key = (f.text, RelationType.ASSOCIATED_WITH, t)
                if key not in seen:
                    relationships.append(
                        ClinicalRelationship(
                            source=f.text,
                            relation=RelationType.ASSOCIATED_WITH,
                            target=t,
                            page=f.page,
                            source_text=f_src,
                        )
                    )
                    seen.add(key)

    # 2. Measurements to Anatomical Structures (MEASURES relation)
    for m in measurements:
        m_name_clean = m.name.strip().lower()
        m_src = m.source_text or f"{m.name}: {m.value}"

        target_anatomy = ECHO_ANATOMY_MAPPINGS.get(m_name_clean)
        if not target_anatomy:
            for k, anat in ECHO_ANATOMY_MAPPINGS.items():
                if re.search(rf"\b{re.escape(k)}\b", m_name_clean):
                    target_anatomy = anat
                    break

        if target_anatomy:
            key = (m.name, RelationType.MEASURES, target_anatomy)
            if key not in seen:
                relationships.append(
                    ClinicalRelationship(
                        source=m.name,
                        relation=RelationType.MEASURES,
                        target=target_anatomy,
                        page=m.page,
                        source_text=m_src,
                    )
                )
                seen.add(key)

    return relationships
