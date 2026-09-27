"""
clinical_extraction/report_rules/lipid_profile.py

Report-type specific extraction rules for Lipid Profile reports.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class LipidProfileRules(BaseReportRules):
    """Extraction rules for Lipid Profile documents."""

    report_type: str = "lipid_profile"

    ANATOMY_PATTERNS: list[str] = [
        "serum",
        "plasma",
        "blood",
    ]

    FINDING_PATTERNS: list[str] = [
        "hypercholesterolemia",
        "dyslipidemia",
        "hypertriglyceridemia",
        "desirable",
        "borderline high",
        "high risk",
        "optimal",
        "near optimal",
        "abnormal lipid profile",
        "normal lipid profile",
    ]
