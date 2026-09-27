"""
clinical_extraction/report_rules/thyroid.py

Report-type specific extraction rules for Thyroid Function Test reports.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class ThyroidRules(BaseReportRules):
    """Extraction rules for Thyroid Function documents."""

    report_type: str = "thyroid_function_test"

    ANATOMY_PATTERNS: list[str] = [
        "thyroid",
        "thyroid gland",
        "serum",
    ]

    FINDING_PATTERNS: list[str] = [
        "hypothyroidism",
        "hyperthyroidism",
        "euthyroid",
        "subclinical hypothyroidism",
        "subclinical hyperthyroidism",
        "thyroiditis",
        "normal thyroid function",
    ]
