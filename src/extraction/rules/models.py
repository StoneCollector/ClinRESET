"""
Data models for the ClinRESET rule extraction pipeline.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ReferenceRange(BaseModel):
    low: Optional[float] = None
    high: Optional[float] = None
    unit: Optional[str] = None
    raw_text: Optional[str] = None


class Measurement(BaseModel):
    value: float
    unit: Optional[str] = None
    reference_range: Optional[ReferenceRange] = None
    raw_text: str


class ExtractedFact(BaseModel):
    fact_id: str
    concept: str
    assertion: str = Field(description="'PRESENT', 'ABSENT', or 'NORMAL'")
    measurement: Optional[Measurement] = None
    source_text: str
    clause_id: Optional[str] = None
    page_number: int = 1
    section_name: Optional[str] = None
    confidence: float = 1.0

    def to_scorer_dict(self) -> dict:
        """Converts to evaluation scorer representation."""
        return {
            "concept": self.concept,
            "assertion": self.assertion,
            "value": self.measurement.value if self.measurement else None,
            "unit": self.measurement.unit if self.measurement else None,
        }
