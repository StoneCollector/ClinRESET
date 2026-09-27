"""
clinical_extraction/report_rules/liver_function.py

Report-type specific extraction rules for Liver Function Test reports.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class LiverFunctionRules(BaseReportRules):
    """Extraction rules for Liver Function Test documents."""

    report_type: str = "liver_function_test"

    ANATOMY_PATTERNS: list[str] = [
        "liver",
        "hepatic",
        "biliary",
        "gallbladder",
        "serum",
    ]

    FINDING_PATTERNS: list[str] = [
        "jaundice",
        "hyperbilirubinemia",
        "elevated transaminases",
        "hepatocellular injury",
        "cholestasis",
        "hypoalbuminemia",
        "normal liver enzymes",
        "normal liver function",
    ]
