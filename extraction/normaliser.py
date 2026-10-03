"""
Output normaliser.

Converts raw extractor output into the stable ExtractionResult JSON
contract consumed by all downstream NLP components.

Design rules
------------
- Fields are NEVER invented.  Missing data → None.
- Page traceability is preserved at every level.
- Tables are parsed from Markdown pipe syntax when available, and from
  coordinate-extractor pipe-separated lines otherwise.
- Measurements are extracted only when name + value can be reliably
  associated via document structure (table row or labelled value).
- No medical interpretation is performed.

The normaliser is intentionally separated from the extractors so that
the same normalisation logic applies regardless of which extractor
produced the raw content.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from extraction.models import (
    DocumentMeta,
    ExtractionResult,
    Measurement,
    RawOutput,
    Section,
    Table,
    TableRow,
    ValidationResult,
)
from extraction.inspector import InspectionResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section parsing helpers
# ---------------------------------------------------------------------------


def _parse_sections_from_markdown(
    page_chunks: list[dict],
) -> list[Section]:
    """
    Parse sections from PyMuPDF4LLM page chunks.

    Each chunk has a "text" key containing Markdown for that page and
    a "metadata" dict with a "page" key (0-indexed).

    Headings (# H1, ## H2, …) delimit sections.  Content between
    headings belongs to the most recent heading.  Content before any
    heading is placed in a synthetic "preamble" section.
    """
    sections: list[Section] = []

    for chunk in page_chunks:
        meta = chunk.get("metadata", {})
        # pymupdf4llm uses 'page_number' (1-indexed) in chunk metadata.
        page_num: Optional[int] = meta.get("page_number", meta.get("page", None))
        # If page_num came from 'page' (0-indexed fallback), convert it.
        if page_num is not None and meta.get("page_number") is None:
            page_num += 1

        text = chunk.get("text", "")
        lines = text.splitlines()

        current_title: Optional[str] = None
        current_lines: list[str] = []

        def _flush():
            body = "\n".join(current_lines).strip()
            if body or current_title:
                sections.append(
                    Section(title=current_title, page=page_num, text=body)
                )

        for line in lines:
            # Markdown heading
            heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
            if heading_match:
                _flush()
                current_title = heading_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        _flush()

    return sections


def _parse_sections_from_plain_text(
    pages: list[dict],
) -> list[Section]:
    """
    Parse sections from plain-text coordinate-extractor output.

    Pages have {"page": int, "text": str}.  ALL-CAPS lines (or lines
    ending with ':') are treated as potential section headings.
    """
    sections: list[Section] = []

    heading_pattern = re.compile(
        r"^[A-Z][A-Z\s\-/\.]{3,}(?:\s*:)?\s*$"
    )

    for page_dict in pages:
        page_num: int = page_dict["page"]
        lines = page_dict["text"].splitlines()

        current_title: Optional[str] = None
        current_lines: list[str] = []

        def _flush():
            body = "\n".join(current_lines).strip()
            if body or current_title:
                sections.append(
                    Section(title=current_title, page=page_num, text=body)
                )

        for line in lines:
            stripped = line.strip()
            if heading_pattern.match(stripped) and len(stripped) > 4:
                _flush()
                current_title = stripped.rstrip(":")
                current_lines = []
            else:
                current_lines.append(line)

        _flush()

    return sections


# ---------------------------------------------------------------------------
# Table parsing helpers
# ---------------------------------------------------------------------------


def _parse_markdown_tables(
    markdown: str, page_chunks: list[dict]
) -> list[Table]:
    """
    Parse pipe-delimited Markdown tables from PyMuPDF4LLM output.

    Page numbers are resolved by mapping character offsets in the full
    Markdown string back to the page boundary markers inserted by
    PyMuPDF4LLMExtractor.
    """
    tables: list[Table] = []

    # Split the Markdown on page markers so we know which page each
    # table comes from.
    page_sections = re.split(r"<!-- page (\d+) -->", markdown)

    current_page: Optional[int] = None
    for segment in page_sections:
        # Odd segments (after split) are page number strings.
        stripped = segment.strip()
        if re.match(r"^\d+$", stripped):
            current_page = int(stripped)
            continue

        # Search for Markdown tables in this segment.
        table_blocks = _extract_markdown_table_blocks(segment)
        for block_lines, preceding_text in table_blocks:
            table = _parse_single_markdown_table(
                block_lines, preceding_text, current_page
            )
            if table:
                tables.append(table)

    return tables


def _extract_markdown_table_blocks(
    text: str,
) -> list[tuple[list[str], str]]:
    """
    Find Markdown table blocks in a text segment.

    Returns a list of (table_lines, preceding_text) tuples.
    'preceding_text' is the nearest non-blank text before the table
    (used as a candidate title).
    """
    lines = text.splitlines()
    results: list[tuple[list[str], str]] = []
    i = 0
    recent_text_lines: list[str] = []

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|"):
            # Collect contiguous table lines.
            block: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            preceding = "\n".join(recent_text_lines[-3:]).strip()
            results.append((block, preceding))
            recent_text_lines = []
        else:
            if line.strip():
                recent_text_lines.append(line.strip())
            i += 1

    return results


def _parse_single_markdown_table(
    block_lines: list[str],
    preceding_text: str,
    page: Optional[int],
) -> Optional[Table]:
    """
    Parse a single block of Markdown table lines into a Table object.

    Returns None if the block does not look like a valid table.
    """
    if len(block_lines) < 2:
        return None

    rows: list[list[str]] = []
    for line in block_lines:
        # Skip separator rows.
        if re.match(r"^\|[\s\-:|]+\|", line.strip()):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return None

    headers = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []

    # Build TableRow objects by mapping columns to known field names.
    col_map = _build_column_map(headers)
    table_rows: list[TableRow] = []

    for raw_row in data_rows:
        tr = _map_row_to_table_row(raw_row, headers, col_map)
        table_rows.append(tr)

    # Attempt to infer a title from the preceding text.
    title = _infer_table_title(preceding_text, headers)

    return Table(
        title=title,
        page=page,
        headers=headers,
        rows=table_rows,
        raw_rows=[headers] + [
            [c.strip() for c in l.strip("|").split("|")]
            for l in block_lines
            if not re.match(r"^\|[\s\-:|]+\|", l.strip())
        ],
    )


def _parse_coordinate_tables(pages: list[dict]) -> list[Table]:
    """
    Extract table-like content from coordinate-extractor plain text.

    The coordinate extractor inserts " | " between columns.  Lines
    containing " | " are treated as potential table rows.
    """
    tables: list[Table] = []

    for page_dict in pages:
        page_num = page_dict["page"]
        lines = page_dict["text"].splitlines()

        table_lines: list[str] = []
        preceding_text_lines: list[str] = []

        def _flush_table():
            nonlocal table_lines
            if len(table_lines) >= 2:
                headers_raw = [c.strip() for c in table_lines[0].split("|")]
                headers = [h.strip() for h in headers_raw if h.strip()]
                col_map = _build_column_map(headers)
                table_rows: list[TableRow] = []
                raw_rows: list[list[str]] = [headers]

                for row_line in table_lines[1:]:
                    cells = [c.strip() for c in row_line.split("|") if c.strip() != ""]
                    raw_rows.append(cells)
                    tr = _map_row_to_table_row(cells, headers, col_map)
                    table_rows.append(tr)

                title = _infer_table_title(
                    "\n".join(preceding_text_lines[-3:]), headers
                )
                tables.append(
                    Table(
                        title=title,
                        page=page_num,
                        headers=headers,
                        rows=table_rows,
                        raw_rows=raw_rows,
                    )
                )
            table_lines = []

        for line in lines:
            stripped = line.strip()
            if " | " in stripped:
                table_lines.append(stripped)
            else:
                _flush_table()
                if stripped:
                    preceding_text_lines.append(stripped)

        _flush_table()

    return tables


def _strip_md(text: str) -> str:
    """
    Strip Markdown formatting (bold, italic, underline, inline code)
    from a table cell value.

    This ensures that cells like '**60 %**' or '*(55-74%)*' are
    normalised to '60 %' and '(55-74%)' respectively before
    field mapping.
    """
    # Remove bold/italic markers.
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}(.*?)_{1,2}", r"\1", text)
    # Remove HTML underline tags inserted by some versions of pymupdf4llm.
    text = re.sub(r"<u>(.*?)</u>", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>\s*", " ", text, flags=re.IGNORECASE)
    # Remove inline code.
    text = re.sub(r"`(.*?)`", r"\1", text)
    return text.strip()


def _build_column_map(headers: list[str]) -> dict[str, int]:
    """
    Map standard field names to column indices based on header text.
    Returns a dict with keys from {"name", "value", "unit", "reference_range"}.
    """
    mapping: dict[str, int] = {}

    name_patterns = re.compile(
        r"\b(measurements?|parameters?|tests?|names?|descriptions?)\b", re.IGNORECASE
    )
    value_patterns = re.compile(
        r"\b(value|result|finding|reading)\b", re.IGNORECASE
    )
    unit_patterns = re.compile(
        r"\b(units?|u|nit)\b", re.IGNORECASE
    )
    ref_patterns = re.compile(
        r"\b(reference|range|ref|expected|normal\s+values?|refere|nce)\b", re.IGNORECASE
    )

    # Strip Markdown from headers before keyword matching.
    clean_headers = [_strip_md(h) for h in headers]

    for i, h in enumerate(clean_headers):
        if name_patterns.search(h) and "name" not in mapping:
            mapping["name"] = i
        elif value_patterns.search(h) and "value" not in mapping:
            mapping["value"] = i
        elif unit_patterns.search(h) and "unit" not in mapping:
            mapping["unit"] = i
        elif ref_patterns.search(h) and "reference_range" not in mapping:
            mapping["reference_range"] = i

    # Fallback: when 'value' is still unmapped, assign the first column that
    # is neither the name column nor the reference_range column and whose
    # header is blank (unnamed columns are commonly the value column in
    # medical report tables like the echocardiography report).
    if "value" not in mapping:
        used = set(mapping.values())
        for i, h in enumerate(clean_headers):
            if i not in used and h.strip() == "":
                mapping["value"] = i
                break

    return mapping


def _map_row_to_table_row(
    cells: list[str],
    headers: list[str],
    col_map: dict[str, int],
) -> TableRow:
    """
    Map a list of cell values to a TableRow using col_map.
    Extra columns that do not map to standard fields are stored in
    TableRow.extra keyed by their header name.

    Cell values have Markdown formatting stripped before storage so
    that downstream components receive clean text.
    """
    # Strip Markdown from all cells.
    clean_cells = [_strip_md(c) for c in cells]

    def _get(field: str) -> Optional[str]:
        idx = col_map.get(field)
        if idx is not None and idx < len(clean_cells):
            val = clean_cells[idx].strip()
            return val if val else None
        return None

    # Determine extra columns.
    used_indices = set(col_map.values())
    extra: dict[str, str] = {}
    for i, cell in enumerate(clean_cells):
        if i not in used_indices and i < len(headers):
            key = _strip_md(headers[i]) if i < len(headers) else f"col_{i}"
            val = cell.strip()
            if val:
                extra[key] = val

    return TableRow(
        name=_get("name"),
        value=_get("value"),
        unit=_get("unit"),
        reference_range=_get("reference_range"),
        extra=extra,
    )


def _infer_table_title(preceding_text: str, headers: list[str]) -> Optional[str]:
    """
    Attempt to infer a table title from the nearest preceding text.
    Returns None if no plausible title can be determined.
    """
    if not preceding_text.strip():
        return None

    # Take the last non-blank line of the preceding text as the title
    # candidate.
    candidates = [l.strip() for l in preceding_text.splitlines() if l.strip()]
    if candidates:
        candidate = candidates[-1]
        # Reject candidates that look like data rows.
        if " | " not in candidate and len(candidate) < 120:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Measurement extraction
# ---------------------------------------------------------------------------


def _extract_measurements_from_tables(
    tables: list[Table],
) -> list[Measurement]:
    """
    Extract Measurement objects from parsed tables.

    Only rows where name + value are both non-None are promoted.
    No medical interpretation is performed.
    No fields are fabricated.
    """
    measurements: list[Measurement] = []

    for table in tables:
        for row in table.rows:
            if row.name and row.value:
                # Attempt to split value and unit if they appear together
                # e.g. "60 %" → value="60", unit="%"
                value_str, unit_str = _split_value_unit(row.value)

                # If the row already has an explicit unit column, prefer it.
                effective_unit = row.unit if row.unit else unit_str

                measurements.append(
                    Measurement(
                        name=row.name,
                        value=value_str,
                        unit=effective_unit,
                        reference_range=row.reference_range,
                        page=table.page,
                        source_section=table.title,
                    )
                )

    return measurements


def _split_value_unit(value_str: str) -> tuple[str, Optional[str]]:
    """
    Attempt to separate a numeric value from a unit suffix.

    Examples:
        "60 %"    → ("60", "%")
        "32.5%"   → ("32.5", "%")
        "23"      → ("23", None)
        "1.47m/s" → ("1.47", "m/s")

    No fabrication: if the split is ambiguous, return the full string
    as the value and None as the unit.
    """
    pattern = re.match(
        r"^(\d+(?:\.\d+)?)\s*(%|mm|cm|m/s|mmHg|l|mg|dl|g|IU|U/L|u/l|bpm)$",
        value_str.strip(),
        re.IGNORECASE,
    )
    if pattern:
        return pattern.group(1), pattern.group(2)
    return value_str.strip(), None


# ---------------------------------------------------------------------------
# Main normaliser
# ---------------------------------------------------------------------------


def normalise(
    raw_result: dict[str, Any],
    inspection: InspectionResult,
    validation_status: str,
    validation_warnings: list[str],
    validation_scores: dict,
) -> ExtractionResult:
    """
    Convert raw extractor output into an ExtractionResult.

    Parameters
    ----------
    raw_result:
        Dict returned by PyMuPDF4LLMExtractor.extract() or
        CoordinateExtractor.extract().
    inspection:
        The InspectionResult from the PDF inspector.
    validation_status, validation_warnings, validation_scores:
        Output from the extraction validator.
    """
    extractor_name: str = raw_result.get("extractor", "unknown")
    is_markdown_extractor = extractor_name == "pymupdf4llm"

    # ---- Raw output ----
    if is_markdown_extractor:
        markdown = raw_result.get("markdown", "")
        plain_text = _markdown_to_plain(markdown)
    else:
        markdown = ""
        plain_text = raw_result.get("text", "")

    raw_output = RawOutput(text=plain_text, markdown=markdown)

    # ---- Document metadata ----
    doc_meta = DocumentMeta(
        file_name=inspection.file_name,
        page_count=inspection.page_count,
        source_type=inspection.source_type,
        extractor=extractor_name,
    )

    # ---- Sections ----
    if is_markdown_extractor:
        page_chunks = raw_result.get("pages", [])
        sections = _parse_sections_from_markdown(page_chunks)
    else:
        pages = raw_result.get("pages", [])
        sections = _parse_sections_from_plain_text(pages)

    # ---- Tables ----
    if is_markdown_extractor:
        page_chunks = raw_result.get("pages", [])
        tables = _parse_markdown_tables(markdown, page_chunks)
    else:
        pages = raw_result.get("pages", [])
        tables = _parse_coordinate_tables(pages)

    # ---- Measurements ----
    measurements = _extract_measurements_from_tables(tables)

    # ---- Validation ----
    validation = ValidationResult(
        status=validation_status,
        warnings=validation_warnings,
        scores=validation_scores,
    )

    return ExtractionResult(
        document=doc_meta,
        sections=sections,
        tables=tables,
        measurements=measurements,
        raw=raw_output,
        validation=validation,
    )


def _markdown_to_plain(markdown: str) -> str:
    """
    Convert Markdown to approximate plain text for the raw.text field.

    This is a simple heuristic conversion; the full Markdown is always
    preserved in raw.markdown.
    """
    # Remove Markdown headings markers but keep the text.
    text = re.sub(r"^#{1,6}\s+", "", markdown, flags=re.MULTILINE)
    # Remove bold/italic markers.
    text = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}(.*?)_{1,2}", r"\1", text)
    # Remove page marker comments.
    text = re.sub(r"<!-- page \d+ -->", "", text)
    return text.strip()
