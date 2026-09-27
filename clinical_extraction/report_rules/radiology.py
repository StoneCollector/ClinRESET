"""
clinical_extraction/report_rules/radiology.py

Report-type specific extraction rules for Radiology reports.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class RadiologyRules(BaseReportRules):
    """Extraction rules for Radiology documents."""

    report_type: str = "radiology"

    ANATOMY_PATTERNS: list[str] = [
        "lung",
        "lungs",
        "pleura",
        "mediastinum",
        "heart",
        "cardiac silhouette",
        "costophrenic angle",
        "diaphragm",
        "trachea",
        "chest",
        "abdomen",
        "pelvis",
        "spine",
        "brain",
        "bone",
        "soft tissue",
    ]

    FINDING_PATTERNS: list[str] = [
        "consolidation",
        "infiltrate",
        "opacity",
        "effusion",
        "pleural effusion",
        "pneumothorax",
        "atelectasis",
        "nodule",
        "mass",
        "cardiomegaly",
        "fracture",
        "edema",
        "pulmonary edema",
        "calcification",
        "granuloma",
        "lymphadenopathy",
        "no focal consolidation",
        "no pleural effusion",
        "no pneumothorax",
        "clear lungs",
        "normal study",
    ]
