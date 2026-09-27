"""
clinical_extraction/report_rules/ecg.py

Report-type specific extraction rules for ECG reports.
"""

from __future__ import annotations

from clinical_extraction.report_rules.base import BaseReportRules


class ECGRules(BaseReportRules):
    """Extraction rules for Electrocardiogram documents."""

    report_type: str = "ecg"

    ANATOMY_PATTERNS: list[str] = [
        "heart",
        "sinus node",
        "atrium",
        "ventricle",
        "bundle branch",
        "anterior wall",
        "inferior wall",
        "lateral wall",
        "septal",
    ]

    FINDING_PATTERNS: list[str] = [
        "normal sinus rhythm",
        "sinus tachycardia",
        "sinus bradycardia",
        "sinus arrhythmia",
        "atrial fibrillation",
        "atrial flutter",
        "left bundle branch block",
        "right bundle branch block",
        "LBBB",
        "RBBB",
        "ST elevation",
        "ST depression",
        "T wave inversion",
        "QT prolongation",
        "premature ventricular contractions",
        "premature atrial contractions",
        "left ventricular hypertrophy",
        "poor R wave progression",
        "normal ecg",
    ]
