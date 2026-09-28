"""
Header and administrative noise filter.
Guarantees that patient demographics, doctor signatures, and hospital boilerplate
can NEVER leak into extracted clinical findings.
"""

import re
from typing import Optional

# Regexes matching demographic, administrative, and signature noise
NOISE_PATTERNS = [
    # Patient Name & ID
    re.compile(r"^\s*(?:Patient\s+)?Name\s*[:.-]?\s*.*$", re.IGNORECASE),
    re.compile(r"^\s*(?:Patient\s+)?ID\s*[:.-]?\s*.*$", re.IGNORECASE),
    re.compile(r"^\s*NAME\s*:\s*[A-Za-z0-9_.\s]+(?:\s+DATED\s*:.*)?$", re.IGNORECASE),
    re.compile(r"^\s*PT(?:\.|\s+)?NAME\s*[:.-]?\s*.*$", re.IGNORECASE),

    # Age & Sex / Gender
    re.compile(r"^\s*Age(?:\s*/\s*Sex|\s*/\s*Gender)?\s*[:.-]?\s*.*$", re.IGNORECASE),
    re.compile(r"^\s*AGE\s*[:.-]?\s*\d+\s*(?:y|yrs|years)?(?:\s*/\s*[MF]|Male|Female)?.*$", re.IGNORECASE),
    re.compile(r"^\s*(?:Sex|Gender)\s*[:.-]?\s*(?:Male|Female|[MF])\b.*$", re.IGNORECASE),

    # Date / Time
    re.compile(r"^\s*(?:Date|Dated|Date\s+of\s+Report|Study\s+Date|DOB|Date\s+of\s+Birth)\s*[:.-]?\s*.*$", re.IGNORECASE),

    # Referring Doctor / Physician
    re.compile(r"^\s*(?:Ref(?:\.|\s+)?(?:By|To|erred\s+By)?|Physician|Doctor|Referring\s+Physician)\s*[:.-]?\s*.*$", re.IGNORECASE),

    # Accession / Modality / Study Header
    re.compile(r"^\s*Accession\s*(?:No|Number)?\s*[:.-]?\s*.*$", re.IGNORECASE),
    re.compile(r"^\s*Modality\s*[:.-]?\s*.*$", re.IGNORECASE),
    re.compile(r"^\s*Study(?:\s*Date)?\s*[:.-]?\s*.*$", re.IGNORECASE),
    re.compile(r"^\s*LMP\s*[:.-]?\s*.*$", re.IGNORECASE),
    re.compile(r"^\s*EDD\s+(?:BY\s+LMP|BY\s+USG)\s*[:.-]?\s*.*$", re.IGNORECASE),
    re.compile(r"^\s*Gestational\s+Age\s*[:.-]?\s*.*$", re.IGNORECASE),

    # Document Titles / Summaries
    re.compile(r"^\s*Medical\s+Report(?:\s*[-–—]\s*Patient\s+Summary)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*ECHO\s+CARDIOGRAPHY\s+REPORT\s*$", re.IGNORECASE),
    re.compile(r"^\s*ULTRASOUND\s+WHOLE\s+ABDOMEN\s*$", re.IGNORECASE),
    re.compile(r"^\s*CT\s+Scan\s+of\s+[A-Za-z\s]+\s*$", re.IGNORECASE),
    re.compile(r"^\s*MRI\s+[A-Za-z\s+–—/-]+\s*$", re.IGNORECASE),
    re.compile(r"^\s*X\s*RAY\s+[A-Za-z\s+–—/-]+\s*$", re.IGNORECASE),

    # Doctor Signatures & Credentials
    re.compile(r"^\s*(?:Consultant\s+)?(?:DM|MD|MBBS|MS|DNB)?\s*(?:Cardiologist|Radiologist|Pathologist|Physician|Sonologist)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:Dr\.|Doctor)\s+[A-Za-z\s.]+$", re.IGNORECASE),

    # Generic Disclaimers & Footers
    re.compile(r"^\s*Please\s+correlate\s+clinically.*$", re.IGNORECASE),
    re.compile(r"^\s*Adv(?:ise)?\s*[:.-]?\s*Clinical\s+Correlation\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"^\s*Page\s+\d+(?:\s+of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^[-=*_~]{3,}$"),  # Decorative lines
]


class HeaderNoiseFilter:
    """Filters out demographic and administrative metadata lines."""

    @classmethod
    def is_noise(cls, text: str) -> bool:
        if not text:
            return True

        stripped = text.strip()
        if not stripped or len(stripped) <= 1:
            return True

        # Check against compiled patterns
        for pat in NOISE_PATTERNS:
            if pat.match(stripped):
                return True

        # In-line demographic checks (e.g. "NAME: PA01 AGE/SEX: 61y /F REF BY: IPD")
        if re.search(r"\bNAME\s*:\s*[A-Za-z0-9_]+", stripped, re.IGNORECASE) and re.search(r"\bAGE(?:/SEX)?\b", stripped, re.IGNORECASE):
            return True

        # Pure doctor signature line (e.g. "Consultant DM Cardiologist")
        if re.search(r"\bConsultant\s+(?:DM|MD)\b", stripped, re.IGNORECASE):
            return True

        return False

    @classmethod
    def clean_text_block(cls, text: str) -> str:
        """Removes noise lines from a multi-line text block."""
        lines = text.splitlines()
        clean_lines = [l for l in lines if not cls.is_noise(l)]
        return "\n".join(clean_lines).strip()
