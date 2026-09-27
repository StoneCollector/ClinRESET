"""
clinical_extraction/report_rules/general_note.py

Report-type specific extraction rules for general narrative clinical notes
(e.g., outpatient consultations, patient summaries with Chief Complaint,
Clinical Observations, Preliminary Diagnosis, Recommendations, and vitals).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from clinical_extraction.entities import create_finding
from clinical_extraction.models import ClinicalFinding, ClinicalMeasurement
from clinical_extraction.negation import detect_assertion, split_into_clauses
from clinical_extraction.normalization import normalize_term
from clinical_extraction.report_rules.base import BaseReportRules


class GeneralNoteRules(BaseReportRules):
    """Extraction rules tailored for general narrative clinical notes."""

    report_type: str = "general_clinical_note"

    ANATOMY_PATTERNS: list[str] = [
        "face",
        "ovary",
        "ovaries",
        "pelvis",
        "pelvic",
        "chest",
        "arm",
        "left arm",
        "heart",
        "lung",
        "lungs",
        "lower right lobe",
        "lobe",
        "abdomen",
        "skin",
    ]

    FINDING_PATTERNS: list[str] = [
        # Symptoms and clinical complaints from real samples
        "irregular menstrual cycles",
        "irregular cycles",
        "menstrual irregularity",
        "weight gain",
        "recent weight gain",
        "mild acne",
        "acne",
        "hirsutism",
        "intense chest pain",
        "mild chest pain",
        "chest pain",
        "shortness of breath",
        "dizziness",
        "pale and diaphoretic",
        "diaphoretic",
        "pale",
        "persistent coughing",
        "coughing",
        "cough",
        "ST-segment elevation",
        "ST elevation",
        "breathing sounds slightly diminished",
        "diminished breathing sounds",
        "visible abnormalities",
        "ovarian cysts",
        "cysts",
        # Preliminary diagnoses / conditions
        "Polycystic Ovary Syndrome",
        "PCOS",
        "Acute Myocardial Infarction",
        "Heart Attack",
        "STEMI",
        "pneumonia",
        "early-stage pneumonia",
        # General examination findings
        "normal",
        "abnormal",
        "unremarkable",
        "within normal limits",
    ]

    def extract_findings(
        self,
        sections: list[Any],
    ) -> list[ClinicalFinding]:
        """Extract narrative findings, observations, and diagnoses with assertion status."""
        findings: list[ClinicalFinding] = []
        seen: set[tuple[str, Optional[int]]] = set()

        for sec in sections:
            sec_text = getattr(sec, "text", "") or ""
            sec_title = getattr(sec, "title", None)
            sec_page = getattr(sec, "page", None)

            if not sec_text:
                continue

            # Process line by line or clause by clause, ignoring administrative headers
            for raw_line in sec_text.splitlines():
                line = raw_line.strip(" \t\r\n")
                if not line or line.startswith(("-", "•", "*")):
                    line = line.lstrip("-•* \t")

                # Skip administrative or purely demographic lines
                if re.match(r"^(?:Patient Name|Age|Gender|Physician|Date)\s*:", line, re.IGNORECASE):
                    continue

                clauses = split_into_clauses(line)
                for clause in clauses:
                    clause_clean = clause.strip(" -•*#_:,.;\t\r\n")
                    if not clause_clean or len(clause_clean) < 2:
                        continue

                    # Don't extract vitals lines as findings
                    if re.match(r"^Vitals\s*:\s*BP\b", clause_clean, re.IGNORECASE):
                        continue

                    for pat in self.FINDING_PATTERNS:
                        regex = re.compile(rf"\b{re.escape(pat)}\b", re.IGNORECASE)
                        match = regex.search(clause_clean)
                        if match:
                            assertion, is_negated = detect_assertion(clause_clean, pat)
                            norm = normalize_term(clause_clean, self.report_type)
                            if not norm:
                                norm = normalize_term(pat, self.report_type)

                            key = (clause_clean.lower(), sec_page)
                            if key not in seen:
                                findings.append(
                                    create_finding(
                                        text=clause_clean,
                                        normalized=norm,
                                        assertion=assertion,
                                        negated=is_negated,
                                        page=sec_page,
                                        source_section=sec_title,
                                        source_text=clause_clean,
                                    )
                                )
                                seen.add(key)
                            break

        return findings

    def extract_measurements(
        self,
        sections: list[Any],
        phase1_measurements: Optional[list[Any]] = None,
    ) -> list[ClinicalMeasurement]:
        """Extract structured vitals (BP, Pulse, Temp, BMI, SpO2) from narrative text."""
        measurements: list[ClinicalMeasurement] = []
        seen_keys: set[tuple[str, Any]] = set()

        # Ingest Phase 1 measurements if any (filtering out obvious non-measurements)
        for m in (phase1_measurements or []):
            name = getattr(m, "name", "")
            val = getattr(m, "value", None)
            if not name or val is None:
                continue
            name_lower = name.lower()
            if any(name_lower.endswith(x) for x in ("age", "date", "name", "id", "sex", "dr")):
                continue
            meas = ClinicalMeasurement(
                name=name.strip(),
                value=val,
                unit=getattr(m, "unit", None),
                reference_range=getattr(m, "reference_range", None),
                page=getattr(m, "page", None),
                source_section=getattr(m, "source_section", None),
                source_text=getattr(m, "source_text", None),
                normalized_name=normalize_term(name.strip(), self.report_type),
            )
            measurements.append(meas)
            seen_keys.add((name.strip().lower(), str(val)))

        # Scan section text for vitals
        for sec in sections:
            sec_text = getattr(sec, "text", "") or ""
            sec_title = getattr(sec, "title", None)
            sec_page = getattr(sec, "page", None)
            if not sec_text:
                continue

            for line in sec_text.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue

                # 1. Blood Pressure: e.g. BP 118/76 mmHg or BP: 165/110 mmHg
                bp_matches = re.finditer(r"\b(?:BP|Blood\s*Pressure)\s*[:=]?\s*(\d{2,3}/\d{2,3})\s*(mmHg)?\b", line_str, re.IGNORECASE)
                for bm in bp_matches:
                    val = bm.group(1)
                    key = ("blood pressure", val)
                    if key not in seen_keys:
                        measurements.append(
                            ClinicalMeasurement(
                                name="Blood Pressure",
                                value=val,
                                unit="mmHg",
                                reference_range=None,
                                page=sec_page,
                                source_section=sec_title,
                                source_text=line_str,
                                normalized_name="Blood Pressure",
                            )
                        )
                        seen_keys.add(key)

                # 2. Pulse Rate: e.g. Pulse 82 bpm or Pulse: 102 bpm
                pulse_matches = re.finditer(r"\b(?:Pulse|Heart\s*Rate|Pulse\s*Rate)\s*[:=]?\s*(\d{2,3})\s*(bpm)?\b", line_str, re.IGNORECASE)
                for pm in pulse_matches:
                    val = int(pm.group(1))
                    key = ("pulse", str(val))
                    if key not in seen_keys:
                        measurements.append(
                            ClinicalMeasurement(
                                name="Pulse",
                                value=val,
                                unit="bpm",
                                reference_range=None,
                                page=sec_page,
                                source_section=sec_title,
                                source_text=line_str,
                                normalized_name="Pulse Rate",
                            )
                        )
                        seen_keys.add(key)

                # 3. Temperature: e.g. Temp 98.2°F or Temp 98.6 F
                temp_matches = re.finditer(r"\b(?:Temp|Temperature)\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)\s*(?:°|º)?\s*([FC])\b", line_str, re.IGNORECASE)
                for tm in temp_matches:
                    val = float(tm.group(1)) if "." in tm.group(1) else int(tm.group(1))
                    unit = f"°{tm.group(2).upper()}"
                    key = ("temperature", str(val))
                    if key not in seen_keys:
                        measurements.append(
                            ClinicalMeasurement(
                                name="Temperature",
                                value=val,
                                unit=unit,
                                reference_range=None,
                                page=sec_page,
                                source_section=sec_title,
                                source_text=line_str,
                                normalized_name="Body Temperature",
                            )
                        )
                        seen_keys.add(key)

                # 4. BMI: e.g. BMI: 29.1 or BMI 24.5
                bmi_matches = re.finditer(r"\bBMI\s*[:=]?\s*(\d{1,2}(?:\.\d+)?)\b", line_str, re.IGNORECASE)
                for bm in bmi_matches:
                    val = float(bm.group(1)) if "." in bm.group(1) else int(bm.group(1))
                    key = ("bmi", str(val))
                    if key not in seen_keys:
                        measurements.append(
                            ClinicalMeasurement(
                                name="BMI",
                                value=val,
                                unit="kg/m²",
                                reference_range=None,
                                page=sec_page,
                                source_section=sec_title,
                                source_text=line_str,
                                normalized_name="Body Mass Index",
                            )
                        )
                        seen_keys.add(key)

                # 5. Oxygen saturation: e.g. Oxygen saturation: 89% or SpO2: 95%
                spo2_matches = re.finditer(r"\b(?:Oxygen\s*saturation|SpO2)\s*[:=]?\s*(\d{1,3})\s*%", line_str, re.IGNORECASE)
                for sm in spo2_matches:
                    val = int(sm.group(1))
                    key = ("oxygen saturation", str(val))
                    if key not in seen_keys:
                        measurements.append(
                            ClinicalMeasurement(
                                name="Oxygen Saturation",
                                value=val,
                                unit="%",
                                reference_range=None,
                                page=sec_page,
                                source_section=sec_title,
                                source_text=line_str,
                                normalized_name="Oxygen Saturation",
                            )
                        )
                        seen_keys.add(key)

        return measurements
