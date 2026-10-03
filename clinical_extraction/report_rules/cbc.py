"""
clinical_extraction/report_rules/cbc.py

Report-type specific extraction rules for Complete Blood Count (CBC) reports.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from clinical_extraction.models import ClinicalMeasurement
from clinical_extraction.report_rules.base import BaseReportRules


class CBCRules(BaseReportRules):
    """Extraction rules for Complete Blood Count documents."""

    report_type: str = "cbc"

    ANATOMY_PATTERNS: list[str] = [
        "blood",
        "bone marrow",
        "peripheral blood",
    ]

    FINDING_PATTERNS: list[str] = [
        "anemia",
        "microcytic",
        "macrocytic",
        "hypochromic",
        "normocytic",
        "normochromic",
        "thrombocytopenia",
        "thrombocytosis",
        "leukocytosis",
        "leukopenia",
        "neutrophilia",
        "neutropenia",
        "lymphocytosis",
        "lymphopenia",
        "eosinophilia",
        "basophilia",
        "anisocytosis",
        "poikilocytosis",
        "target cells",
        "schistocytes",
        "atypical lymphocytes",
        "adequate platelets",
        "platelets adequate",
        "no parasite seen",
        "no hemoparasite",
        "normal blood picture",
    ]

    # Known non-clinical terms that should never be extracted as measurement names
    _NON_CLINICAL_NAMES: frozenset[str] = frozenset({
        "male", "female", "gender", "sex", "age", "normal range",
        "low levels", "high levels", "comment", "remarks", "photometry",
        "method", "technique",
    })

    # Regex for CBC-style tabular rows:
    # "Hemoglobin (Hb) | 14.5 | 13.5 - 17.5 | g/dL"
    # "Hemoglobin (Hb) 14.5 13.5 - 17.5 g/dL Photometry"
    _CBC_ROW_RE = re.compile(
        r"^(?P<name>[A-Za-z][A-Za-z0-9\s\(\)\.\-_/]{2,30}?)\s*\|?\s*"
        r"(?P<value><?>?\s*\d+(?:\.\d+)?)\s*\|?\s*"
        r"(?P<range>\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\s*\|?\s*"
        r"(?P<unit>[a-zA-Z/%]+)",
        re.IGNORECASE | re.MULTILINE
    )

    def extract_measurements(
        self,
        sections: list[Any],
        phase1_measurements: Optional[list[Any]] = None,
    ) -> list[ClinicalMeasurement]:
        from clinical_extraction.filters import filter_measurements, is_admin_field
        from clinical_extraction.normalization import normalize_term

        measurements = super().extract_measurements(sections, phase1_measurements)
        seen_names = {m.name.lower() for m in measurements if m.name}

        for sec in sections:
            sec_text = getattr(sec, "text", "") or ""
            sec_title = getattr(sec, "title", None)
            sec_page = getattr(sec, "page", None)

            for match in self._CBC_ROW_RE.finditer(sec_text):
                name = match.group("name").strip()
                name_lower = name.lower()

                # Quality gates
                if name_lower in seen_names:
                    continue
                if len(name) < 3:
                    continue
                if is_admin_field(name):
                    continue
                if name_lower in self._NON_CLINICAL_NAMES:
                    continue

                val_str = match.group("value").strip()
                try:
                    val: Any = float(val_str) if "." in val_str else int(val_str)
                except ValueError:
                    val = val_str

                meas = ClinicalMeasurement(
                    name=name,
                    value=val,
                    unit=match.group("unit").strip(),
                    reference_range=match.group("range").strip(),
                    page=sec_page,
                    source_section=sec_title,
                    source_text=match.group(0).strip(),
                    normalized_name=normalize_term(name, self.report_type),
                    semantic_category="MEASUREMENT"
                )
                measurements.append(meas)
                seen_names.add(name_lower)

        # Final defensive pass: strip any admin / date artefacts
        return filter_measurements(measurements)
