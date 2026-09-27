"""
clinical_extraction/report_rules/radiology.py

Report-type specific extraction rules for Radiology reports (CT, MRI, X-ray, Ultrasound).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from clinical_extraction.models import ClinicalMeasurement
from clinical_extraction.normalization import normalize_term
from clinical_extraction.report_rules.base import BaseReportRules


class RadiologyRules(BaseReportRules):
    """Extraction rules for Radiology documents."""

    report_type: str = "radiology"

    ANATOMY_PATTERNS: list[str] = [
        # Thoracic
        "trachea",
        "bronchi",
        "bronchus",
        "right main bronchus",
        "left main bronchus",
        "lungs",
        "lung",
        "pleura",
        "mediastinum",
        "chest wall",
        "axilla",
        "axillary",
        "thoracic inlet",
        "lung parenchyma",
        "upper lobe",
        "lower lobe",
        "middle lobe",
        "cardiac silhouette",
        "cardio-thoracic ratio",
        "heart",
        # Abdominal & Pelvic
        "liver",
        "gall bladder",
        "gallbladder",
        "cbd",
        "common bile duct",
        "pancreas",
        "mpd",
        "main pancreatic duct",
        "spleen",
        "kidney",
        "kidneys",
        "right kidney",
        "left kidney",
        "renal",
        "adrenal",
        "adrenal gland",
        "urinary bladder",
        "bladder",
        "prostate",
        "peritoneal cavity",
        "retroperitoneum",
        "bowel",
        "bowel loops",
        "calyx",
        "lower calyx",
        "mid calyx",
        "upper calyx",
        "portal vein",
        "hepatic veins",
        "proximal ureter",
        "ureter",
        "ovaries",
        "ovary",
        "uterus",
        "endometrium",
        # Spine & Musculoskeletal
        "vertebrae",
        "vertebra",
        "cervical vertebrae",
        "dorsal vertebrae",
        "lumbar vertebrae",
        "vertebral body",
        "intervertebral disc",
        "intervertebral discs",
        "facet joints",
        "facet joint",
        "facets",
        "facetal joints",
        "spinal cord",
        "cord",
        "cauda equina",
        "conus medullaris",
        "filum terminale",
        "sacroiliac joint",
        "sacroiliac joints",
        "thecal sac",
        "neural foramina",
        "neural foramen",
        "lateral recess",
        "cervical spine",
        "dorsal spine",
        "lumbar spine",
        "pars interarticularis",
        "spinous process",
        "transverse process",
        "pedicle",
        "lamina",
        "iliopsoas",
        "paravertebral soft tissue",
        # Chest X-ray
        "diaphragm",
        "domes of diaphragm",
        "costophrenic angle",
        "costophrenic angles",
        "cp angle",
        "cp angles",
        "hila",
        "hilum",
        "bony thorax",
    ]

    FINDING_PATTERNS: list[str] = [
        "normal",
        "unremarkable",
        "no evidence of",
        "enlarged",
        "mildly enlarged",
        "effusion",
        "pleural effusion",
        "consolidation",
        "atelectasis",
        "compression atelectasis",
        "pneumothorax",
        "pneumomediastinum",
        "ground glass attenuation",
        "ground glass",
        "fatty liver",
        "grade-ii fatty liver",
        "grade -ii fatty liver",
        "grade ii fatty liver",
        "grade-i fatty liver",
        "grade i fatty liver",
        "grade-iii fatty liver",
        "grade iii fatty liver",
        "calculus",
        "calculi",
        "echogenic calculus",
        "echogenic calculi",
        "hydronephrosis",
        "hydrouretronephrosis",
        "dilatation",
        "biliary dilatation",
        "bulge",
        "disc bulge",
        "thickening",
        "pleural thickening",
        "interstitial thickening",
        "wall thickening",
        "lymphadenopathy",
        "osteophytes",
        "marginal osteophytes",
        "subluxation",
        "dislocation",
        "spondylolisthesis",
        "mass",
        "mass lesion",
        "nodule",
        "focal lesion",
        "narrowing",
        "intraluminal mass",
        "infiltrate",
        "opacity",
        "patchy haze",
        "clear",
        "intact",
        "straightened",
        "altered signal intensity",
        "edema",
        "fracture",
        "cyst",
        "defect",
        "sludge",
        "pericholecystic collection",
        "collection",
        "free fluid",
    ]

    def extract_measurements(
        self,
        sections: list[Any],
        phase1_measurements: Optional[list[Any]] = None,
    ) -> list[ClinicalMeasurement]:
        """
        Extract radiology-specific measurements:
        1. MRI spinal canal diameter table (Level row and mm row -> 'Sagittal diameter L1-2').
        2. Inline measurements with '~' prefix and glued units (e.g. '(~15.8cm)', 'Vol~18cc', 'measuring ~4mm').
        3. Existing valid Phase 1 measurements.
        All radiology measurements legitimately have reference_range=None.
        """
        measurements: list[ClinicalMeasurement] = []
        seen: set[tuple[str, Optional[int], Any, Optional[str]]] = set()

        # 1. MRI spinal canal table / inline
        for sec in sections:
            text = getattr(sec, "text", "") or ""
            sec_title = getattr(sec, "title", None)
            sec_page = getattr(sec, "page", None)
            if not text:
                continue

            # Check inline format: Level: L1-2 L2-3 ... / (mm): 15.4 14.5 ...
            m_inline = re.search(
                r"Level\s*:\s*([^\r\n/]+)[\s/]+(?:\(mm\)|mm)\s*:\s*([^\r\n]+)",
                text,
                re.IGNORECASE,
            )
            if m_inline and "|" not in m_inline.group(1):
                levels = m_inline.group(1).split()
                vals = m_inline.group(2).split()
                for lvl, val in zip(levels, vals):
                    try:
                        num_val = float(val) if "." in val else int(val)
                        name = f"Sagittal diameter {lvl}"
                        key = (name.lower(), sec_page, num_val, "mm")
                        if key not in seen:
                            measurements.append(
                                ClinicalMeasurement(
                                    name=name,
                                    value=num_val,
                                    unit="mm",
                                    reference_range=None,
                                    page=sec_page,
                                    source_section=sec_title,
                                    source_text=f"{lvl}: {val} mm",
                                    normalized_name=normalize_term(name, self.report_type),
                                )
                            )
                            seen.add(key)
                    except ValueError:
                        pass

            # Check table format (markdown pipes or multi-line)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for i, line in enumerate(lines):
                if re.search(r"Level\s*[:\|]", line, re.IGNORECASE):
                    for j in range(i + 1, min(i + 4, len(lines))):
                        if re.search(r"\(?mm\)?\s*[:\|]", lines[j], re.IGNORECASE):
                            lvl_line = lines[i]
                            val_line = lines[j]
                            if "|" in lvl_line:
                                levels = [
                                    p.strip("*_ ")
                                    for p in lvl_line.split("|")
                                    if p.strip("*_ ") and not re.search(r"Level", p, re.IGNORECASE)
                                ]
                                vals = [
                                    p.strip("*_ ")
                                    for p in val_line.split("|")
                                    if p.strip("*_ ") and not re.search(r"mm", p, re.IGNORECASE)
                                ]
                            else:
                                levels = [
                                    p
                                    for p in re.findall(
                                        r"[LTCStcs]\d+(?:-[A-Za-z0-9]+)?", lvl_line
                                    )
                                ]
                                vals = [p for p in re.findall(r"\d+(?:\.\d+)?", val_line)]
                            for lvl, val in zip(levels, vals):
                                try:
                                    num_val = float(val) if "." in val else int(val)
                                    name = f"Sagittal diameter {lvl}"
                                    key = (name.lower(), sec_page, num_val, "mm")
                                    if key not in seen:
                                        measurements.append(
                                            ClinicalMeasurement(
                                                name=name,
                                                value=num_val,
                                                unit="mm",
                                                reference_range=None,
                                                page=sec_page,
                                                source_section=sec_title,
                                                source_text=f"{lvl}: {val} mm",
                                                normalized_name=normalize_term(name, self.report_type),
                                            )
                                        )
                                        seen.add(key)
                                except ValueError:
                                    pass

            # 2. Inline measurements in narrative sentences
            for line in lines:
                line_str = line.strip()
                if not line_str or ("Level" in line_str and "(mm)" in line_str) or line_str.startswith("|"):
                    continue

                # Detect subject prefix at start of line: "**Liver: is enlarged..." or "Gall bladder: ..."
                subj_match = re.match(
                    r"^\s*[*_#\s]*([A-Za-z][A-Za-z\s/]{1,30}?)\s*[*_]*\s*:\s*(.*)$",
                    line_str,
                )
                line_subj = subj_match.group(1).strip() if subj_match else None

                # Regex matching:
                # - a number optionally preceded by ~ or Vol~
                # - and immediately or closely followed by unit: cm, mm, cc, ml
                meas_iter = re.finditer(
                    r"(?:(Vol(?:ume)?)\s*)?(?:~\s*|\b)(\d+(?:\.\d+)?)\s*(cm|mm|cc|ml)\b",
                    line_str,
                    re.IGNORECASE,
                )
                for mm in meas_iter:
                    full_match = mm.group(0)
                    prefix_context = line_str[max(0, mm.start() - 3) : mm.start()]
                    is_tilde = "~" in prefix_context or "~" in full_match
                    vol_kw = mm.group(1)
                    val_str = mm.group(2)
                    unit_str = mm.group(3)

                    # Require ~ OR explicit unit (cm, mm, cc, ml) OR Vol
                    if not (is_tilde or vol_kw or (unit_str and unit_str.lower() in ("cm", "mm", "cc", "ml"))):
                        continue

                    start_pos = mm.start()
                    pre_text = line_str[:start_pos]

                    name: Optional[str] = None
                    ctx_m = re.search(
                        r"([A-Za-z][A-Za-z\s]{1,30}?)\s+(?:measuring|size|is|of)\s*$",
                        pre_text,
                        re.IGNORECASE,
                    )
                    if ctx_m and ctx_m.group(1).strip("*_ ").lower() not in (
                        "in", "normal", "enlarged", "is", "and", "with"
                    ):
                        candidate_name = ctx_m.group(1).strip("*_ ")
                        if len(candidate_name.split()) <= 4:
                            name = candidate_name

                    if not name and vol_kw and line_subj:
                        name = f"{line_subj} Volume"
                    elif not name and vol_kw:
                        name = "Volume"
                    elif not name and line_subj:
                        name = line_subj
                    elif not name:
                        prev_kw = re.search(
                            r"\b(calculus|calculi|lesion|mass|cyst|nodule|kidney|spleen|liver|prostate|ovary|uterus)\b",
                            pre_text,
                            re.IGNORECASE,
                        )
                        if prev_kw:
                            name = prev_kw.group(1).capitalize()
                        else:
                            name = "Measurement"

                    name = re.sub(r"[*_#]+", "", name).strip()
                    name = re.sub(
                        r"^(?:is|in|of|a|an|the|two|small|large)\s+",
                        "",
                        name,
                        flags=re.IGNORECASE,
                    ).strip()
                    name = name.title() if name.islower() else name

                    num_val = float(val_str) if "." in val_str else int(val_str)
                    key = (name.lower(), sec_page, num_val, unit_str.lower())
                    if key not in seen:
                        measurements.append(
                            ClinicalMeasurement(
                                name=name,
                                value=num_val,
                                unit=unit_str.lower(),
                                reference_range=None,
                                page=sec_page,
                                source_section=sec_title,
                                source_text=line_str[
                                    max(0, start_pos - 15) : min(len(line_str), mm.end() + 15)
                                ],
                                normalized_name=normalize_term(name, self.report_type),
                            )
                        )
                        seen.add(key)

        # 3. Incorporate valid Phase 1 measurements
        if phase1_measurements:
            admin_pattern = re.compile(
                r"\b(age|sex|gender|date|name|id|ref|physician|doctor|hospital|contact|phone)\b",
                re.IGNORECASE,
            )
            for m in phase1_measurements:
                m_name = getattr(m, "name", "") or ""
                m_val = getattr(m, "value", None)
                if not m_name or m_val is None:
                    continue
                if admin_pattern.search(m_name):
                    continue

                try:
                    num_val = float(m_val) if "." in str(m_val) else int(m_val)
                except ValueError:
                    num_val = m_val

                m_unit = getattr(m, "unit", None)
                m_page = getattr(m, "page", None)
                key = (m_name.strip().lower(), m_page, num_val, (m_unit or "").lower())
                if key not in seen:
                    measurements.append(
                        ClinicalMeasurement(
                            name=m_name.strip(),
                            value=num_val,
                            unit=m_unit.strip() if m_unit else None,
                            reference_range=None,  # Strictly None for radiology
                            page=m_page,
                            source_section=getattr(m, "source_section", None),
                            source_text=f"{m_name}: {m_val}{(' ' + m_unit) if m_unit else ''}",
                            normalized_name=normalize_term(m_name.strip(), self.report_type),
                        )
                    )
                    seen.add(key)

        return measurements
