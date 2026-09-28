"""
Section detector for medical reports.
Splits raw report text into structured clinical sections based on standard headings.
"""

import re
from typing import List, Tuple
from .models import Section

# Canonical section patterns
KNOWN_SECTION_HEADINGS = [
    # Top-level / General
    r"CHIEF COMPLAINT[S]?",
    r"CLINICAL OBSERVATIONS?",
    r"CLINICAL BRIEF",
    r"PRELIMINARY DIAGNOSIS",
    r"RECOMMENDATIONS?",
    r"HISTORY",
    r"PROTOCOL",
    r"INVESTIGATION",
    r"REPORT",
    r"OBSERVATIONS?",
    r"FINDINGS",
    r"IMPRESSION[S]?",
    r"FINAL IMPRESSION[S]?",
    r"ADVISE?",
    
    # Echo specific
    r"ECHO CARDIOGRAPHY REPORT",
    r"M-MODE PARAMETERS",
    r"LEFT VENTRICLE FUNCTION INDICES",
    r"ON INTERROGATING WITH PULSE & CONTINUOUS WAVE DOPPLER IT WAS FOUND THAT THERE IS[:-]?",
    r"DOPPLER",
    r"VALVES?",
    r"OTHERS",
    
    # CT / MRI specific
    r"TRACHEA & BRONCHI",
    r"LUNGS & PLEURA",
    r"MEDIASTINUM",
    r"CHEST WALL & AXILLAE?",
    r"POSTERIOR FOSSA",
    r"SUPRATENTORIAL",
    r"CERVICAL SPINE",
    r"DORSAL SPINE",
    r"LUMBAR SPINE",
    
    # Abdominal organs (US / CT)
    r"LIVER",
    r"GALL BLADDER",
    r"PANCREAS",
    r"SPLEEN",
    r"RIGHT KIDNEY",
    r"LEFT KIDNEY",
    r"KIDNEYS?",
    r"URINARY BLADDER",
    r"PROSTATE",
    r"BOWEL LOOPS?",
    
    # X-ray specific
    r"CHEST PA",
    r"X RAY [A-Z ]+"
]

SECTION_PATTERN = re.compile(
    r"^(?:[#*_\s-]*)(?P<heading>" + "|".join(KNOWN_SECTION_HEADINGS) + r")\s*[:.-]?(?:[#*_\s-]*)$",
    re.IGNORECASE | re.MULTILINE
)


class SectionDetector:
    """Detects and partitions text into clinical sections."""

    @classmethod
    def detect_sections(cls, text: str, page_number: int = 1) -> List[Section]:
        lines = text.splitlines()
        sections: List[Section] = []

        current_heading = "HEADER"
        current_raw_title = "HEADER"
        current_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check if line matches a known heading
            # Case 1: Line is a standalone heading
            heading_match = cls._is_section_header(stripped)

            if heading_match:
                # Flush existing section if it has content
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    is_tbl = cls._is_table_content(current_lines)
                    sections.append(Section(
                        name=current_heading,
                        raw_title=current_raw_title,
                        content=content,
                        lines=list(current_lines),
                        page_number=page_number,
                        is_table=is_tbl
                    ))
                    current_lines = []

                current_heading = cls._normalize_heading(heading_match)
                current_raw_title = stripped
            else:
                current_lines.append(line)

        # Flush last section
        if current_lines:
            content = "\n".join(current_lines).strip()
            is_tbl = cls._is_table_content(current_lines)
            sections.append(Section(
                name=current_heading,
                raw_title=current_raw_title,
                content=content,
                lines=list(current_lines),
                page_number=page_number,
                is_table=is_tbl
            ))

        return sections

    @classmethod
    def _is_section_header(cls, line: str) -> str | None:
        clean = re.sub(r"^[#*_~\s-]+|[#*_~\s:-]+$", "", line).strip()
        if not clean:
            return None

        # Check exact or prefix match against pattern
        for heading_regex in KNOWN_SECTION_HEADINGS:
            pat = r"^" + heading_regex + r"[:\s-]*$"
            if re.match(pat, clean, re.IGNORECASE):
                return clean
        return None

    @classmethod
    def _normalize_heading(cls, raw: str) -> str:
        clean = raw.upper().strip()
        clean = re.sub(r"[:\s-]+$", "", clean)
        if "IMPRESSION" in clean:
            return "IMPRESSION"
        if "DOPPLER" in clean:
            return "DOPPLER"
        if "M-MODE" in clean:
            return "M-MODE PARAMETERS"
        if "RECOMMENDATION" in clean or "ADVISE" in clean:
            return "RECOMMENDATIONS"
        if "CLINICAL OBSERVATION" in clean:
            return "CLINICAL OBSERVATIONS"
        if "OBSERVATION" in clean or "FINDING" in clean:
            return "OBSERVATIONS"
        return clean

    @classmethod
    def _is_table_content(cls, lines: List[str]) -> bool:
        """Determines if lines represent tabular data."""
        table_rows = 0
        for l in lines:
            if "|" in l or re.search(r"\b\d+(?:\.\d+)?\b.*\b\(\d+-\d+[a-zA-Z%]*\)", l):
                table_rows += 1
            elif len(re.findall(r"\s{3,}", l)) >= 2:
                table_rows += 1
        return table_rows >= max(2, len(lines) // 3)
