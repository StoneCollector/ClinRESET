"""
clinical_extraction/report_rules/generic.py

Fallback generic extraction rules for unknown or unspecified medical report types.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class GenericRules(BaseReportRules):
    """Fallback rules when report type is unknown or has no dedicated rule set."""

    report_type: str = "generic"

    ANATOMY_PATTERNS: list[str] = [
        "heart",
        "left ventricle",
        "right ventricle",
        "left atrium",
        "right atrium",
        "interventricular septum",
        "interatrial septum",
        "mitral valve",
        "tricuspid valve",
        "aortic valve",
        "pulmonary valve",
        "lung",
        "lungs",
        "pleura",
        "liver",
        "kidney",
        "kidneys",
        "brain",
        "blood",
        "chest",
        "abdomen",
        "LV",
        "RV",
        "LA",
        "RA",
        "IVS",
        "IAS",
    ]

    FINDING_PATTERNS: list[str] = [
        "unremarkable",
        "normal",
        "within normal limits",
        "abnormal",
        "negative",
        "positive",
        "intact",
        "effusion",
        "mass",
        "vegetation",
        "clot",
        "thrombus",
        "hypertrophy",
        "LVH",
        "Conc LVH",
        "RWMA",
        "LVDD",
        "TR",
        "Mild TR",
        "MR",
        "AR",
        "PR",
        "regurgitation",
        "stenosis",
    ]
