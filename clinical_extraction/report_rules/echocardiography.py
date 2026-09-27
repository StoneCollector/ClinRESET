"""
clinical_extraction/report_rules/echocardiography.py

Report-type specific extraction rules for Echocardiography reports.

Extracts cardiac anatomy, valve observations, functional indices,
and Doppler/pathological findings (e.g., LVH, RWMA, LVDD, regurgitation, effusion).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from clinical_extraction.entities import (
    create_anatomy,
    create_finding,
)
from clinical_extraction.models import (
    AnatomicalEntity,
    ClinicalFinding,
)
from clinical_extraction.negation import detect_assertion, split_into_clauses
from clinical_extraction.normalization import normalize_term
from clinical_extraction.report_rules.base import BaseReportRules


class EchocardiographyRules(BaseReportRules):
    """Extraction rules tailored for echocardiography reports."""

    report_type: str = "echocardiography"

    ANATOMY_PATTERNS: list[str] = [
        "left ventricle",
        "right ventricle",
        "mitral valve",
        "tricuspid valve",
        "aortic valve",
        "pulmonary valve",
        "left atrium",
        "right atrium",
        "interventricular septum",
        "interatrial septum",
        "aortic root",
        "pericardium",
        "pulmonary artery",
        "LVOT",
        "RVOT",
        "IVS",
        "IAS",
        "LV",
        "RV",
        "LA",
        "RA",
    ]

    FINDING_PATTERNS: list[str] = [
        # Hypertrophy / function
        "Conc LVH",
        "concentric LVH",
        "eccentric LVH",
        "LVH",
        "left ventricular hypertrophy",
        "RWMA",
        "regional wall motion abnormality",
        "normal LV function",
        "normal RV function",
        "LV function",
        "RV function",
        "Grade 1 LVDD",
        "Grade 2 LVDD",
        "Grade 3 LVDD",
        "LVDD",
        "diastolic dysfunction",
        # Valvular lesions
        "Mild TR",
        "Moderate TR",
        "Severe TR",
        "TR",
        "tricuspid regurgitation",
        "Mild MR",
        "Moderate MR",
        "Severe MR",
        "MR",
        "mitral regurgitation",
        "Mild AR",
        "Moderate AR",
        "Severe AR",
        "AR",
        "aortic regurgitation",
        "Mild PR",
        "Moderate PR",
        "Severe PR",
        "PR",
        "pulmonary regurgitation",
        "gradient across LVOT",
        "prolapse",
        "stenosis",
        # Masses / fluid / other
        "effusion",
        "pericardial effusion",
        "vegetation",
        "mass",
        "clot",
        "thrombus",
        "intact",
        "midsystolic notch",
    ]

    def extract_findings(
        self,
        sections: list[Any],
    ) -> list[ClinicalFinding]:
        """
        Extract echocardiography findings from Impression, Doppler, Others,
        and Valve description sections.
        """
        findings: list[ClinicalFinding] = []
        seen: set[tuple[str, Optional[int]]] = set()

        def add_finding(text: str, page: Optional[int], section: Optional[str], src: str):
            clean_text = text.strip(" -•*#_:,.;\t\r\n")
            if not clean_text or len(clean_text) < 2:
                return

            # Avoid false positives like dates or headers
            if clean_text.lower() in ("others", "dated", "measurements", "normal values", "ref by"):
                return

            assertion, is_negated = detect_assertion(clean_text)
            norm = normalize_term(clean_text, self.report_type)

            # If clean_text didn't normalize, try searching known findings in it
            if not norm:
                for pat in self.FINDING_PATTERNS:
                    if re.search(rf"\b{re.escape(pat)}\b", clean_text, re.IGNORECASE):
                        norm = normalize_term(pat, self.report_type)
                        if norm:
                            break

            key = (clean_text.lower(), page)
            if key not in seen:
                findings.append(
                    create_finding(
                        text=clean_text,
                        normalized=norm,
                        assertion=assertion,
                        negated=is_negated,
                        page=page,
                        source_section=section,
                        source_text=src,
                    )
                )
                seen.add(key)

        for sec in sections:
            sec_text = getattr(sec, "text", "") or ""
            sec_title = getattr(sec, "title", None)
            sec_page = getattr(sec, "page", None)

            if not sec_text:
                continue

            # Skip table lines
            lines_to_process = []
            for raw_line in sec_text.splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("|"):
                    continue
                lines_to_process.append(stripped)

            for line_str in lines_to_process:
                # Strip markdown bold/italic/underline markers and bullets
                cleaned_line = re.sub(r"[*_~`#]", " ", line_str)
                cleaned_line = re.sub(r"^[-\u2022*]\s*", "", cleaned_line).strip()

                # Remove inline measurements like PASP=34mmHg or EF- 60% from finding text
                cleaned_line = re.sub(r"PASP\s*=\s*\d+\s*(?:mmHg)?\.?", "", cleaned_line, flags=re.IGNORECASE)
                cleaned_line = re.sub(r"EF\s*[-:=]?\s*\d+\s*%", "", cleaned_line, flags=re.IGNORECASE)
                # Remove velocity measurements from finding text
                cleaned_line = re.sub(r"(?:Aortic|Pulmonary)\s+velocity\s*=\s*\d+(?:\.\d+)?\s*m/s", "", cleaned_line, flags=re.IGNORECASE)

                # If line mentions multiple valves, split by valve
                valve_segments = re.split(r"(?=(?:MITRAL|TRICUSPID|AORTIC|PULMONARY)\s+VALVE\b)", cleaned_line, flags=re.IGNORECASE)
                for segment in valve_segments:
                    seg = segment.strip()
                    if not seg:
                        continue

                    # If segment has valve header (e.g. "MITRAL VALVE : Normal"), handle it
                    valve_header_match = re.match(r"^((?:MITRAL|TRICUSPID|AORTIC|PULMONARY)\s+VALVE\s*:\s*)(.*)", seg, re.IGNORECASE)
                    if valve_header_match:
                        valve_name = valve_header_match.group(1).strip(" :")
                        rest = valve_header_match.group(2).strip()
                        # If rest is simple like "Normal", extract finding
                        if rest.lower() in ("normal", "thin. opening well. no prolapse", "normal."):
                            add_finding(f"{valve_name}: {rest}", sec_page, sec_title, line_str)
                            # Also check for sub-findings like "No prolapse"
                            for sub in re.split(r"[.;]+", rest):
                                s = sub.strip()
                                if s and s.lower() not in ("normal", "thin"):
                                    add_finding(s, sec_page, sec_title, line_str)
                            continue

                    # Split sentences by period, semicolon, or multi-No pattern
                    # e.g. "No evidence of any mass / vegetation No effusion No LA/LV clot"
                    pre_split = re.sub(r"(?<=\S)\s+(?=No\s+[A-Za-z])", ". ", seg)
                    sentences = re.split(r"(?<=[.!?])\s+|[;]+", pre_split)

                    for sentence in sentences:
                        sent = sentence.strip(" .")
                        if not sent:
                            continue

                        # Split by comma if comma separates distinct findings (e.g. "Conc LVH, No RWMA")
                        clauses = re.split(r",\s*(?=(?:no|not|normal|with|without|mild|moderate|severe|grade)\b)", sent, flags=re.IGNORECASE)
                        for clause in clauses:
                            c = clause.strip(" ,.-;")
                            if not c or len(c) < 2:
                                continue

                            # Clean attached phrase artifacts like 'Mitral inflow' from LVOT gradient
                            if re.search(r"gradient across LVOT", c, re.IGNORECASE):
                                c = re.sub(r"\s+Mitral\s+inflow\b.*", "", c, flags=re.IGNORECASE).strip()

                            # Filter out non-finding fragments
                            if c.lower() in ("mitral inflow", "e <a", "dated", "others", "normal values", "measurements"):
                                continue

                            # Match against known finding patterns or explicit negation/normal statements
                            matched = False
                            for pat in self.FINDING_PATTERNS:
                                if re.search(rf"\b{re.escape(pat)}\b", c, re.IGNORECASE):
                                    add_finding(c, sec_page, sec_title, line_str)
                                    matched = True
                                    break

                            if not matched:
                                if re.search(r"\b(?:no|without|intact|normal)\b", c, re.IGNORECASE):
                                    add_finding(c, sec_page, sec_title, line_str)

        return findings
