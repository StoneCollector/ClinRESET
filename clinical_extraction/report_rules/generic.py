"""
clinical_extraction/report_rules/generic.py

Fallback generic extraction rules for unknown or unspecified medical report types.
Contains only broad, report-type-agnostic anatomy and finding vocabulary.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class GenericRules(BaseReportRules):
    """Fallback rules when report type is unknown or has no dedicated rule set."""

    report_type: str = "generic"

    ANATOMY_PATTERNS: list[str] = [
        "heart",
        "lung",
        "lungs",
        "pleura",
        "liver",
        "gallbladder",
        "gall bladder",
        "spleen",
        "pancreas",
        "kidney",
        "kidneys",
        "urinary bladder",
        "bladder",
        "prostate",
        "brain",
        "spine",
        "vertebrae",
        "bone",
        "bones",
        "chest",
        "abdomen",
        "pelvis",
        "blood",
        "soft tissue",
    ]

    FINDING_PATTERNS: list[str] = [
        "normal",
        "abnormal",
        "unremarkable",
        "within normal limits",
        "positive",
        "negative",
        "intact",
        "effusion",
        "mass",
        "lesion",
        "nodule",
        "cyst",
        "infection",
        "inflammation",
        "edema",
        "swelling",
        "pain",
        "tenderness",
    ]
