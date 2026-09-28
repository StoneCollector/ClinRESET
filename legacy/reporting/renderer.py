"""
reporting/renderer.py

Render FinalReport to formatted dictionaries or representations.
"""

from __future__ import annotations

from typing import Any

from reporting.models import FinalReport


def render_report(final_report: FinalReport) -> dict[str, Any]:
    """Render a FinalReport instance to its dictionary output."""
    return final_report.to_dict()
