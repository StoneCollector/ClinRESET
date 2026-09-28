"""
reporting/__init__.py

Top-level reporting package for assembling visual, structured clinical reports.
"""

from __future__ import annotations

from reporting.builder import build_final_report
from reporting.models import FinalReport
from reporting.renderer import render_report

__all__ = [
    "FinalReport",
    "build_final_report",
    "render_report",
]
