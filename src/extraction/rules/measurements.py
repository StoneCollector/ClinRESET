"""
Deterministic measurement parser and grammar.
Extracts numerical measurements, units, and in-situ reference ranges from clinical text.
Never relies on LLMs or guessing.
"""

import re
from typing import Optional, List, Tuple
from .models import Measurement, ReferenceRange

# Regex for in-situ reference range e.g. (20-37mm), (06-11mm), (55-74%)
RANGE_PATTERN = re.compile(
    r"\(\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*([a-zA-Z%]*)\s*\)",
    re.IGNORECASE
)

# Standard units in clinical reports
UNITS_REGEX = r"(?:mm|cm|m/s|mmHg|bpm|°F|%|cc|ml)"


class MeasurementParser:
    """Parses clinical measurements, units, and ranges deterministically."""

    @classmethod
    def parse_in_situ_range_measurement(cls, text: str) -> Optional[Tuple[str, Measurement]]:
        """
        Parses measurements accompanied by explicit reference ranges:
        e.g. 'Aortic root diameter 23 (20-37mm)'
        e.g. 'Ejection Fraction 60 % (55-74%)'
        Returns: (concept_prefix, Measurement)
        """
        range_match = RANGE_PATTERN.search(text)
        if not range_match:
            return None

        low_val = float(range_match.group(1))
        high_val = float(range_match.group(2))
        range_unit = range_match.group(3).strip() or None

        # Look for the measured value immediately preceding the range
        prefix_text = text[:range_match.start()].strip()
        val_match = re.search(r"(\d+(?:\.\d+)?)\s*(%|mm|cm)?\s*$", prefix_text)
        if not val_match:
            return None

        val = float(val_match.group(1))
        unit = val_match.group(2) or range_unit

        concept_prefix = prefix_text[:val_match.start()].strip(" :.-")

        ref_range = ReferenceRange(
            low=low_val,
            high=high_val,
            unit=range_unit,
            raw_text=range_match.group(0)
        )

        measurement = Measurement(
            value=val,
            unit=unit,
            reference_range=ref_range,
            raw_text=text[val_match.start():range_match.end()]
        )

        return concept_prefix, measurement

    @classmethod
    def parse_blood_pressure(cls, text: str) -> Optional[Tuple[Measurement, Measurement]]:
        """
        Parses systolic and diastolic BP: 'BP 118/76 mmHg' -> (systolic, diastolic)
        """
        bp_match = re.search(r"\bBP\s*[:.-]?\s*(\d{2,3})\s*/\s*(\d{2,3})\s*(mmHg)?\b", text, re.IGNORECASE)
        if not bp_match:
            return None

        sys_val = float(bp_match.group(1))
        dia_val = float(bp_match.group(2))
        unit = "mmHg"

        m_sys = Measurement(value=sys_val, unit=unit, raw_text=f"{int(sys_val)} {unit}")
        m_dia = Measurement(value=dia_val, unit=unit, raw_text=f"{int(dia_val)} {unit}")

        return m_sys, m_dia

    @classmethod
    def parse_key_value_measurement(cls, text: str) -> Optional[Tuple[str, Measurement]]:
        """
        Parses key-value measurements:
        e.g. 'PASP=34mmHg', 'Aortic Velocity = 1.47 m/s', 'Pulse 82 bpm', 'Temp 98.2°F', 'BMI: 29.1'
        """
        # Specific named vitals/cardiac patterns
        patterns = [
            # Key = Value Unit
            (r"\b([A-Za-z][A-Za-z0-9\s/–-]{1,25}?)\s*[:=-]\s*~?\s*(\d+(?:\.\d+)?)\s*(" + UNITS_REGEX + r")?\b"),
            # Measuring ~ X mm / cm
            (r"\b([A-Za-z][A-Za-z0-9\s/–-]{1,25}?)\s+measuring\s*~?\s*(\d+(?:\.\d+)?)\s*(" + UNITS_REGEX + r")\b"),
            # Key in size (~Xcm)
            (r"\b([A-Za-z][A-Za-z0-9\s/–-]{1,25}?)\s*(?:is\s+[a-z\s]+)?in\s+size\s*\([~-]?\s*(\d+(?:\.\d+)?)\s*(" + UNITS_REGEX + r")\b"),
            # Shrunken (13 cm)
            (r"\b([A-Za-z][A-Za-z0-9\s/–-]{1,25}?)\s*\([~-]?\s*(\d+(?:\.\d+)?)\s*(" + UNITS_REGEX + r")\b"),
            # Vol~22cc
            (r"\b([A-Za-z][A-Za-z0-9\s/–-]{1,25}?)\s*\(Vol\s*~?\s*(\d+(?:\.\d+)?)\s*(" + UNITS_REGEX + r")\b"),
        ]

        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                concept = match.group(1).strip(" :.-")
                val = float(match.group(2))
                unit = match.group(3).strip() if match.group(3) else None
                meas = Measurement(
                    value=val,
                    unit=unit,
                    reference_range=None,
                    raw_text=match.group(0)
                )
                return concept, meas

        # Standalone vital signs like "Pulse 82 bpm", "Temp 98.2°F"
        vitals = [
            (r"\bPulse\s*[:.-]?\s*(\d{2,3})\s*(bpm)?\b", "heart rate", "bpm"),
            (r"\bTemp(?:erature)?\s*[:.-]?\s*(\d{2,3}(?:\.\d+)?)\s*(?:°F|F)?\b", "body temperature", "°F"),
            (r"\bOxygen\s+saturation\s*[:.-]?\s*(\d{1,3})\s*%?\b", "oxygen saturation", "%"),
            (r"\bBMI\s*[:.-]?\s*(\d{1,2}(?:\.\d+)?)\b", "body mass index", None),
        ]

        for pat, concept, default_unit in vitals:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                meas = Measurement(value=val, unit=default_unit, reference_range=None, raw_text=m.group(0))
                return concept, meas

        return None
