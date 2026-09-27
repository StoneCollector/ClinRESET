"""
clinical_extraction/report_rules/__init__.py

Registry and factory for report-type specific extraction rules.
"""

from __future__ import annotations

from typing import Optional

from clinical_extraction.report_rules.base import BaseReportRules
from clinical_extraction.report_rules.cbc import CBCRules
from clinical_extraction.report_rules.echocardiography import EchocardiographyRules
from clinical_extraction.report_rules.ecg import ECGRules
from clinical_extraction.report_rules.generic import GenericRules
from clinical_extraction.report_rules.kidney_function import KidneyFunctionRules
from clinical_extraction.report_rules.lipid_profile import LipidProfileRules
from clinical_extraction.report_rules.liver_function import LiverFunctionRules
from clinical_extraction.report_rules.radiology import RadiologyRules
from clinical_extraction.report_rules.thyroid import ThyroidRules


RULE_REGISTRY: dict[str, type[BaseReportRules]] = {
    "echocardiography": EchocardiographyRules,
    "echo": EchocardiographyRules,
    "cbc": CBCRules,
    "complete_blood_count": CBCRules,
    "lipid_profile": LipidProfileRules,
    "lipid": LipidProfileRules,
    "liver_function_test": LiverFunctionRules,
    "liver_function": LiverFunctionRules,
    "lft": LiverFunctionRules,
    "renal_function_test": KidneyFunctionRules,
    "kidney_function": KidneyFunctionRules,
    "rft": KidneyFunctionRules,
    "kft": KidneyFunctionRules,
    "thyroid_function_test": ThyroidRules,
    "thyroid": ThyroidRules,
    "tft": ThyroidRules,
    "ecg": ECGRules,
    "ekg": ECGRules,
    "radiology": RadiologyRules,
    "generic": GenericRules,
}


def get_rules_for_report_type(report_type: Optional[str]) -> BaseReportRules:
    """
    Retrieve an instantiated rule engine for the given report type.

    Falls back to GenericRules if the report type is unknown or None.
    """
    if not report_type:
        return GenericRules()

    key = str(report_type).strip().lower()
    rule_cls = RULE_REGISTRY.get(key, GenericRules)
    return rule_cls()


__all__ = [
    "BaseReportRules",
    "EchocardiographyRules",
    "CBCRules",
    "LipidProfileRules",
    "LiverFunctionRules",
    "KidneyFunctionRules",
    "ThyroidRules",
    "ECGRules",
    "RadiologyRules",
    "GenericRules",
    "get_rules_for_report_type",
]
