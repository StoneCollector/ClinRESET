"""
Report Segmenter for ClinRESET.
Integrates section processing, header noise filtering, and clause splitting
into a clean stream of atomic clinical clauses with full provenance.
"""

import re
from pathlib import Path
from typing import List, Optional
from src.parsing.models import ParsedDocument, Section
from .models import Clause
from .header_filter import HeaderNoiseFilter
from .clause_splitter import ClauseSplitter


class ReportSegmenter:
    """Segments parsed medical documents into clean, atomic clinical clauses."""

    @classmethod
    def segment_document(cls, doc: ParsedDocument) -> List[Clause]:
        clauses: List[Clause] = []
        file_stem = Path(doc.file_name).stem

        for s_idx, section in enumerate(doc.sections):
            sec_name = section.name
            page_num = section.page_number

            # If section is primarily a table (e.g. M-MODE PARAMETERS), process rows
            if section.is_table or "M-MODE" in sec_name:
                table_clauses = cls._process_table_section(section, file_stem, s_idx, page_num)
                clauses.extend(table_clauses)
            else:
                narrative_clauses = cls._process_narrative_section(section, file_stem, s_idx, page_num)
                clauses.extend(narrative_clauses)

        return clauses

    @classmethod
    def _process_narrative_section(cls, section: Section, file_stem: str, sec_idx: int, page_num: int) -> List[Clause]:
        clauses: List[Clause] = []
        c_count = 0

        # Filter lines for noise first
        clean_lines = []
        for line in section.lines:
            if not HeaderNoiseFilter.is_noise(line):
                clean_lines.append(line.strip())

        if not clean_lines:
            return []

        section_text = " ".join(clean_lines)
        raw_clauses = ClauseSplitter.split(section_text)

        for raw_c in raw_clauses:
            # Secondary check on clause itself to guarantee no leakage
            if HeaderNoiseFilter.is_noise(raw_c):
                continue

            cleaned_text = cls._normalize_clause_text(raw_c)
            if not cleaned_text or len(cleaned_text) < 2:
                continue

            c_count += 1
            clause_id = f"{file_stem}:p{page_num}:s{sec_idx}:c{c_count}"
            clauses.append(Clause(
                clause_id=clause_id,
                text=cleaned_text,
                raw_text=raw_c,
                page_number=page_num,
                section_name=section.name,
                is_table_row=False,
                source_file=file_stem
            ))

        return clauses

    @classmethod
    def _process_table_section(cls, section: Section, file_stem: str, sec_idx: int, page_num: int) -> List[Clause]:
        """Processes vertical or markdown table rows into consolidated measurement clauses."""
        clauses: List[Clause] = []
        lines = [l.strip() for l in section.lines if l.strip() and not HeaderNoiseFilter.is_noise(l)]

        # Check for pipe-delimited tables
        pipe_rows = [l for l in lines if "|" in l]
        if pipe_rows:
            return cls._process_pipe_table(pipe_rows, section.name, file_stem, sec_idx, page_num)

        # Handle vertical multi-line measurement tables (e.g. line 1: name, line 2: val, line 3: range)
        # Look for measurement name followed by value followed by (range)
        idx = 0
        c_count = 0
        while idx < len(lines):
            line = lines[idx]
            # Check if this line is a heading/label or measurement
            # Pattern: Name, next line number, next line (min-max unit)
            if idx + 2 < len(lines):
                next1 = lines[idx + 1]
                next2 = lines[idx + 2]
                if re.match(r"^\d+(?:\.\d+)?\s*%?$", next1) and re.match(r"^\(\d+-\d+[a-zA-Z%]*\)$", next2):
                    combined = f"{line} {next1} {next2}"
                    c_count += 1
                    clause_id = f"{file_stem}:p{page_num}:s{sec_idx}:c{c_count}"
                    clauses.append(Clause(
                        clause_id=clause_id,
                        text=combined,
                        raw_text=combined,
                        page_number=page_num,
                        section_name=section.name,
                        is_table_row=True,
                        source_file=file_stem
                    ))
                    idx += 3
                    continue

            # Check if line itself contains name + value + range
            if re.search(r"\b\d+(?:\.\d+)?\b.*\b\(\d+-\d+[a-zA-Z%]*\)", line):
                c_count += 1
                clause_id = f"{file_stem}:p{page_num}:s{sec_idx}:c{c_count}"
                clauses.append(Clause(
                    clause_id=clause_id,
                    text=line,
                    raw_text=line,
                    page_number=page_num,
                    section_name=section.name,
                    is_table_row=True,
                    source_file=file_stem
                ))
                idx += 1
                continue

            # Fallback for standard measurement rows
            if re.search(r"\b\d+(?:\.\d+)?\s*(?:mm|cm|%|m/s|mmHg|bpm|cc)\b", line, re.IGNORECASE):
                c_count += 1
                clause_id = f"{file_stem}:p{page_num}:s{sec_idx}:c{c_count}"
                clauses.append(Clause(
                    clause_id=clause_id,
                    text=line,
                    raw_text=line,
                    page_number=page_num,
                    section_name=section.name,
                    is_table_row=True,
                    source_file=file_stem
                ))
            idx += 1

        return clauses

    @classmethod
    def _process_pipe_table(cls, rows: List[str], sec_name: str, file_stem: str, sec_idx: int, page_num: int) -> List[Clause]:
        clauses: List[Clause] = []
        c_count = 0
        for row in rows:
            parts = [p.strip() for p in row.split("|") if p.strip()]
            if not parts or any("---" in p for p in parts):
                continue
            if any(h in parts[0].upper() for h in ["MEASUREMENT", "NORMAL VALUE", "PARAMETER"]):
                continue

            line = " ".join(parts)
            c_count += 1
            clause_id = f"{file_stem}:p{page_num}:s{sec_idx}:c{c_count}"
            clauses.append(Clause(
                clause_id=clause_id,
                text=line,
                raw_text=row,
                page_number=page_num,
                section_name=sec_name,
                is_table_row=True,
                source_file=file_stem
            ))
        return clauses

    @classmethod
    def _normalize_clause_text(cls, text: str) -> str:
        # Strip leading bullet points or numbers
        clean = re.sub(r"^[•*–—\-]\s*", "", text).strip()
        clean = re.sub(r"^\d+\.\s*", "", clean).strip()
        return clean
