"""
reporting/models.py

Data models for the final patient/clinician visual report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FinalReport:
    """
    Consolidated final report model containing summary, key findings,
    measurements of interest, contextual relationships, and limitations.
    """

    report_summary: dict[str, Any]
    key_findings: list[dict[str, Any]] = field(default_factory=list)
    measurements_of_interest: list[dict[str, Any]] = field(default_factory=list)
    context: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize final report to dictionary."""
        return {
            "report_summary": dict(self.report_summary),
            "key_findings": list(self.key_findings),
            "measurements_of_interest": list(self.measurements_of_interest),
            "context": list(self.context),
            "limitations": list(self.limitations),
        }
