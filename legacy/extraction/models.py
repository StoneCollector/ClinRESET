"""
Data models for the extraction layer.

These are the stable, serialisable data structures that form the
contract between the extraction layer and all downstream NLP components.

Design rules
------------
- Fields are never invented/inferred beyond what the source document
  provides.
- Missing optional fields are represented as None, not fabricated.
- Every section, table, and measurement retains page traceability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    # Imported only for type hints; avoids circular dependency at runtime.
    from classification.models import ClassificationResult


# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------


@dataclass
class DocumentMeta:
    """Technical metadata about the source PDF."""

    file_name: str
    page_count: int
    source_type: str          # "digital_pdf" | "scanned_pdf" | "unknown"
    extractor: str            # "pymupdf4llm" | "coordinate" | "ocr" | "none"


@dataclass
class TableRow:
    """A single data row inside a structured table."""

    name: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    # Preserve any extra columns that do not map to the standard fields.
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class Table:
    """A table extracted from the document."""

    title: Optional[str]
    page: Optional[int]
    headers: list[str] = field(default_factory=list)
    rows: list[TableRow] = field(default_factory=list)
    # Raw cell matrix for tables that cannot be cleanly parsed.
    raw_rows: list[list[str]] = field(default_factory=list)


@dataclass
class Section:
    """A logical section of the report (heading + body text)."""

    title: Optional[str]
    page: Optional[int]
    text: str = ""
    # References to table indices inside ExtractionResult.tables.
    table_refs: list[int] = field(default_factory=list)


@dataclass
class Measurement:
    """
    A single measurement/value/unit/reference-range tuple.

    No field is fabricated: absent fields are None.
    """

    name: Optional[str]
    value: Optional[str]
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    page: Optional[int] = None
    source_section: Optional[str] = None


@dataclass
class RawOutput:
    """Preserved raw extractor output."""

    text: str = ""
    markdown: str = ""


@dataclass
class ValidationResult:
    """Result of the extraction validation step."""

    status: str                                  # "GOOD" | "DEGRADED" | "FAILED"
    warnings: list[str] = field(default_factory=list)
    scores: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    """
    The normalised intermediate representation produced by the
    extraction layer.

    This is the CONTRACT between the extraction layer and all future
    clinical NLP components.

    Phase 2 extension
    -----------------
    The ``classification`` field is populated by the classification layer
    after extraction.  It is None until Phase 2 runs and is omitted from
    the serialised dict when absent, so existing extraction-only consumers
    are unaffected.
    """

    document: DocumentMeta
    sections: list[Section] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    raw: RawOutput = field(default_factory=RawOutput)
    validation: ValidationResult = field(
        default_factory=lambda: ValidationResult(status="FAILED")
    )
    # Set by the classification layer (Phase 2); None until then.
    classification: Optional[Any] = field(default=None, repr=False)
    # Set by the clinical extraction layer (Phase 3); None until then.
    clinical_information: Optional[Any] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """
        Return a plain-dict representation suitable for JSON serialisation.

        Field order follows the canonical report.json layout:
            document → classification (if present) → clinical_information (if present)
            → sections → tables → measurements → raw → validation
        """
        result: dict[str, Any] = {
            "document": {
                "file_name": self.document.file_name,
                "page_count": self.document.page_count,
                "source_type": self.document.source_type,
                "extractor": self.document.extractor,
            },
        }

        # Phase 2: insert classification immediately after document metadata
        # when available.  Omit the key entirely when Phase 2 has not run.
        if self.classification is not None:
            if hasattr(self.classification, "to_dict"):
                result["classification"] = self.classification.to_dict()
            else:
                result["classification"] = self.classification

        # Phase 3: insert clinical_information after classification when available.
        # Omit the key entirely when Phase 3 has not run.
        if self.clinical_information is not None:
            if hasattr(self.clinical_information, "to_dict"):
                result["clinical_information"] = self.clinical_information.to_dict()
            else:
                result["clinical_information"] = self.clinical_information

        result.update({
            "sections": [
                {
                    "title": s.title,
                    "page": s.page,
                    "text": s.text,
                    "table_refs": s.table_refs,
                }
                for s in self.sections
            ],
            "tables": [
                {
                    "title": t.title,
                    "page": t.page,
                    "headers": t.headers,
                    "rows": [
                        {
                            "name": r.name,
                            "value": r.value,
                            "unit": r.unit,
                            "reference_range": r.reference_range,
                            **({} if not r.extra else {"extra": r.extra}),
                        }
                        for r in t.rows
                    ],
                    "raw_rows": t.raw_rows,
                }
                for t in self.tables
            ],
            "measurements": [
                {
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "reference_range": m.reference_range,
                    "page": m.page,
                    "source_section": m.source_section,
                }
                for m in self.measurements
            ],
            "raw": {
                "text": self.raw.text,
                "markdown": self.raw.markdown,
            },
            "validation": {
                "status": self.validation.status,
                "warnings": self.validation.warnings,
                "scores": self.validation.scores,
            },
        })

        return result
