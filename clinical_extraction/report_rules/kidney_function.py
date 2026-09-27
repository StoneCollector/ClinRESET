"""
clinical_extraction/report_rules/kidney_function.py

Report-type specific extraction rules for Renal / Kidney Function Test reports.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class KidneyFunctionRules(BaseReportRules):
    """Extraction rules for Renal Function Test documents."""

    report_type: str = "renal_function_test"

    ANATOMY_PATTERNS: list[str] = [
        "kidney",
        "renal",
        "serum",
        "urine",
    ]

    FINDING_PATTERNS: list[str] = [
        "azotemia",
        "uremia",
        "hyperkalemia",
        "hypokalemia",
        "hypernatremia",
        "hyponatremia",
        "hyperuricemia",
        "renal impairment",
        "acute kidney injury",
        "chronic kidney disease",
        "normal renal function",
        "normal electrolytes",
    ]
