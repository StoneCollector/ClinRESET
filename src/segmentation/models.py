"""
Data models for the ClinRESET segmentation pipeline.
"""

from pydantic import BaseModel, Field


class Clause(BaseModel):
    """
    Represents an atomic clinical clause or statement extracted from a report.
    Carries complete provenance (file, page, section).
    """
    clause_id: str = Field(description="Unique deterministic ID, e.g. echo_PA01:p1:sec2:c1")
    text: str = Field(description="Normalized, clean clause text")
    raw_text: str = Field(description="Original clause text prior to normalization")
    page_number: int = Field(description="1-based page number")
    section_name: str = Field(description="Normalized section heading")
    is_table_row: bool = Field(default=False, description="True if extracted from tabular measurement row")
    source_file: str = Field(description="Source report file name")
