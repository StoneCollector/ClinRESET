"""
Data models for the ClinRESET parsing pipeline.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Section(BaseModel):
    """Represents a discrete section within a medical report."""
    name: str = Field(description="Normalized section name, e.g. OBSERVATIONS, IMPRESSION")
    raw_title: str = Field(description="Original header text from report")
    content: str = Field(description="Raw text content of the section")
    lines: List[str] = Field(default_factory=list, description="Non-empty lines in section")
    page_number: int = Field(default=1, description="1-based page index where section starts")
    is_table: bool = Field(default=False, description="True if section is primarily tabular data")


class ParsedPage(BaseModel):
    """Represents extracted text and layout of a single PDF page."""
    page_number: int = Field(description="1-based page number")
    raw_text: str = Field(description="Full text extracted from the page")
    char_count: int = Field(description="Total characters extracted")
    extraction_method: str = Field(default="digital", description="'digital' or 'ocr'")
    sections: List[Section] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    """Represents the complete parsed report with extracted sections and metadata."""
    file_path: str
    file_name: str
    page_count: int
    full_text: str
    extraction_method: str = Field(default="digital", description="'digital', 'ocr', or 'hybrid'")
    pages: List[ParsedPage] = Field(default_factory=list)
    sections: List[Section] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
