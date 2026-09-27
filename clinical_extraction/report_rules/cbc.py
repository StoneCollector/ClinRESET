"""
clinical_extraction/report_rules/cbc.py

Report-type specific extraction rules for Complete Blood Count (CBC) reports.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class CBCRules(BaseReportRules):
    """Extraction rules for Complete Blood Count documents."""

    report_type: str = "cbc"

    ANATOMY_PATTERNS: list[str] = [
        "blood",
        "bone marrow",
        "peripheral blood",
    ]

    FINDING_PATTERNS: list[str] = [
        "anemia",
        "microcytic",
        "macrocytic",
        "hypochromic",
        "normocytic",
        "normochromic",
        "thrombocytopenia",
        "thrombocytosis",
        "leukocytosis",
        "leukopenia",
        "neutrophilia",
        "neutropenia",
        "lymphocytosis",
        "lymphopenia",
        "eosinophilia",
        "basophilia",
        "anisocytosis",
        "poikilocytosis",
        "target cells",
        "schistocytes",
        "atypical lymphocytes",
        "adequate platelets",
        "platelets adequate",
        "no parasite seen",
        "no hemoparasite",
        "normal blood picture",
    ]
