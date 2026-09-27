"""
classification/signatures.py

Configurable report-type signature definitions.

Each ReportSignature describes the weighted evidence patterns that
identify a specific medical report type.  The classifier consumes
these signatures without being aware of individual report types —
adding a new report type requires only adding a new signature here.

Weight scale (guidance, not hard constraint)
--------------------------------------------
  Title match      : 15   — explicit report title
  Section title    : 8–10 — section headings that are type-defining
  Table title      : 6–8  — table headers that are type-defining
  Measurement name : 5–6  — highly specific measurement names
  Strong keyword   : 4–5  — specialist vocabulary, very low false-positive rate
  Supporting kw    : 1–2  — common vocabulary, higher false-positive rate

A direct title match deliberately outweighs any combination of generic
supporting keywords so that, e.g., "ECHO CARDIOGRAPHY REPORT" as a
document title cannot be overridden by a CBC that happens to mention "LV".

Exclusion patterns
------------------
Each signature may optionally list exclusion patterns (strings whose
presence in a dominant signal source penalises that signature's score).
Exclusions are applied as a multiplier reduction, not a hard block,
so that a single irrelevant mention cannot force a wrong classification.

This module is the ONLY place to edit when adding new report types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SignalGroup:
    """
    A group of patterns that share the same weight within a signature.

    Attributes
    ----------
    patterns:
        List of strings to search for (case-insensitive substring match).
    weight:
        Score contribution per matched pattern (first match per pattern
        counts; multiple occurrences of the same pattern are not stacked).
    category:
        Human-readable category label used in evidence records.
    """

    patterns: list[str]
    weight: float
    category: str


@dataclass
class ReportSignature:
    """
    Complete signature for a single report type.

    Attributes
    ----------
    canonical_name:
        The authoritative identifier returned in ClassificationResult.
    aliases:
        Alternative names / common abbreviations (display only).
    title_patterns:
        Patterns matched against the document title / primary section title.
        These carry the highest weight.
    section_patterns:
        Patterns matched against all section titles.
    table_patterns:
        Patterns matched against all table titles and column headers.
    measurement_patterns:
        Patterns matched against normalised measurement names.
    strong_keyword_groups:
        One or more SignalGroups of high-specificity keywords.
    supporting_keyword_groups:
        One or more SignalGroups of lower-specificity keywords.
    exclusion_patterns:
        Patterns whose presence in the raw text reduce the candidate score
        by applying a penalty multiplier (see EXCLUSION_PENALTY).
    min_score_threshold:
        Minimum raw score required before this signature is considered a
        viable candidate.  Prevents a handful of generic terms from
        triggering a false-positive classification.
    """

    canonical_name: str
    aliases: list[str]
    title_patterns: list[str]
    section_patterns: list[str]
    table_patterns: list[str]
    measurement_patterns: list[str]
    strong_keyword_groups: list[SignalGroup] = field(default_factory=list)
    supporting_keyword_groups: list[SignalGroup] = field(default_factory=list)
    exclusion_patterns: list[str] = field(default_factory=list)
    min_score_threshold: float = 5.0


# ---------------------------------------------------------------------------
# Weights for the structured fields
# (shared across all signatures; individual SignalGroups override keyword wts)
# ---------------------------------------------------------------------------

TITLE_WEIGHT = 15.0
SECTION_TITLE_WEIGHT = 9.0
TABLE_TITLE_WEIGHT = 7.0
MEASUREMENT_NAME_WEIGHT = 5.0

# Score reduction multiplier applied when an exclusion pattern is found.
# 0.5 = 50 % penalty on the raw score (not a hard block).
EXCLUSION_PENALTY = 0.50


# ---------------------------------------------------------------------------
# Signature definitions
# ---------------------------------------------------------------------------


ECHOCARDIOGRAPHY = ReportSignature(
    canonical_name="echocardiography",
    aliases=["Echo", "Echocardiogram", "ECHO", "2D Echo", "Transthoracic Echo"],

    title_patterns=[
        "ECHO CARDIOGRAPHY REPORT",
        "ECHOCARDIOGRAPHY REPORT",
        "ECHO REPORT",
        "2D ECHO REPORT",
        "TRANSTHORACIC ECHOCARDIOGRAPHY",
        "ECHOCARDIOGRAM",
        "ECHOCARDIOGRAPHY",
    ],

    section_patterns=[
        "M-MODE PARAMETERS",
        "M MODE PARAMETERS",
        "DOPPLER",
        "PULSE AND CONTINUOUS WAVE DOPPLER",
        "CONTINUOUS WAVE DOPPLER",
        "FINAL IMPRESSION",          # only strong in context of echo-specific content
        "LEFT VENTRICLE FUNCTION",
        "ECHO CARDIOGRAPHY REPORT",
        "ECHOCARDIOGRAPHY REPORT",
    ],

    table_patterns=[
        "M-MODE PARAMETERS",
        "M MODE PARAMETERS",
        "LEFT VENTRICLE FUNCTION",
        "EJECTION FRACTION",
        "MEASUREMENTS",              # lower weight — also appears in other reports
    ],

    measurement_patterns=[
        "Ejection Fraction",
        "Fractional shortening",
        "Aortic root diameter",
        "Left Atrial diameter",
        "Left Ventricular ED Dimension",
        "Left Ventricular ES Dimension",
        "Inter Vent. Septum thickness",
        "LVposterior wall thickness",
        "LV posterior wall thickness",
        "PASP",
        "E/A ratio",
        "Deceleration time",
        "LVOT",
        "Aortic Velocity",
        "Pulmonary velocity",
    ],

    strong_keyword_groups=[
        SignalGroup(
            patterns=[
                "Ejection Fraction", "EF", "Fractional Shortening",
                "M-MODE", "M MODE",
                "ECHO CARDIOGRAPHY", "ECHOCARDIOGRAPHY",
            ],
            weight=5.0,
            category="strong_keyword",
        ),
        SignalGroup(
            patterns=[
                "PASP", "LVDD", "LVH", "RWMA",
                "Doppler",
                "mitral inflow", "aortic regurgitation",
                "pulmonary regurgitation",
                "IAS", "IVS",
            ],
            weight=4.0,
            category="strong_keyword",
        ),
    ],

    supporting_keyword_groups=[
        SignalGroup(
            patterns=[
                "LV function", "RV function", "LV", "RV",
                "mitral valve", "tricuspid valve", "aortic valve", "pulmonary valve",
                "cardiologist",
                "regurgitation", "vegetation", "effusion",
                "wall motion", "clot",
            ],
            weight=1.5,
            category="supporting_keyword",
        ),
    ],

    exclusion_patterns=[
        # If the doc clearly says CBC / LFT / thyroid, penalise echo score.
        "haemoglobin", "hemoglobin", "platelet", "WBC", "bilirubin",
        "TSH", "T3", "T4", "creatinine", "urea",
    ],

    min_score_threshold=8.0,
)


CBC = ReportSignature(
    canonical_name="cbc",
    aliases=["Complete Blood Count", "Full Blood Count", "CBC", "FBC", "Haematology"],

    title_patterns=[
        "COMPLETE BLOOD COUNT",
        "COMPLETE BLOOD PICTURE",
        "FULL BLOOD COUNT",
        "CBC",
        "FBC",
        "HAEMATOLOGY REPORT",
        "BLOOD COUNT REPORT",
    ],

    section_patterns=[
        "COMPLETE BLOOD COUNT",
        "HAEMATOLOGY",
        "BLOOD INDICES",
        "RED CELL INDICES",
        "WHITE CELL DIFFERENTIAL",
        "DIFFERENTIAL COUNT",
    ],

    table_patterns=[
        "COMPLETE BLOOD COUNT",
        "HAEMATOLOGY",
        "BLOOD COUNT",
        "DIFFERENTIAL",
        "HAEMOGLOBIN",
    ],

    measurement_patterns=[
        "Haemoglobin", "Hemoglobin", "Hb",
        "WBC", "White Blood Cell", "White Blood Count",
        "RBC", "Red Blood Cell", "Red Blood Count",
        "Platelet", "Platelet Count",
        "Haematocrit", "Hematocrit", "HCT",
        "MCV", "MCH", "MCHC",
        "Neutrophils", "Lymphocytes", "Monocytes", "Eosinophils", "Basophils",
        "Reticulocyte",
    ],

    strong_keyword_groups=[
        SignalGroup(
            patterns=[
                "Haemoglobin", "Hemoglobin",
                "WBC", "RBC",
                "Platelet Count", "Platelet",
                "MCV", "MCH", "MCHC",
                "Haematocrit", "Hematocrit",
            ],
            weight=5.0,
            category="strong_keyword",
        ),
        SignalGroup(
            patterns=[
                "Neutrophils", "Lymphocytes", "Monocytes",
                "Eosinophils", "Basophils",
                "Differential",
                "Reticulocyte",
            ],
            weight=4.0,
            category="strong_keyword",
        ),
    ],

    supporting_keyword_groups=[
        SignalGroup(
            patterns=[
                "blood count", "blood picture",
                "g/dL", "g/L", "10^3", "fL",
            ],
            weight=1.5,
            category="supporting_keyword",
        ),
    ],

    exclusion_patterns=[
        "ejection fraction", "ECHO", "bilirubin", "TSH", "creatinine",
        "cholesterol", "triglyceride",
    ],

    min_score_threshold=8.0,
)


LIPID_PROFILE = ReportSignature(
    canonical_name="lipid_profile",
    aliases=["Lipid Panel", "Cholesterol Panel", "Lipid Profile"],

    title_patterns=[
        "LIPID PROFILE",
        "LIPID PANEL",
        "CHOLESTEROL PANEL",
        "LIPID REPORT",
        "FASTING LIPID PROFILE",
    ],

    section_patterns=[
        "LIPID PROFILE",
        "CHOLESTEROL",
        "LIPID PANEL",
    ],

    table_patterns=[
        "LIPID PROFILE",
        "CHOLESTEROL",
        "TRIGLYCERIDE",
    ],

    measurement_patterns=[
        "Total Cholesterol",
        "LDL Cholesterol", "LDL-C", "LDL",
        "HDL Cholesterol", "HDL-C", "HDL",
        "VLDL",
        "Triglycerides", "Triglyceride",
        "Non-HDL Cholesterol",
        "LDL/HDL Ratio",
        "Total/HDL Ratio",
        "Cholesterol/HDL",
    ],

    strong_keyword_groups=[
        SignalGroup(
            patterns=[
                "Total Cholesterol", "Cholesterol",
                "LDL", "HDL", "VLDL",
                "Triglycerides", "Triglyceride",
            ],
            weight=5.0,
            category="strong_keyword",
        ),
        SignalGroup(
            patterns=[
                "LDL/HDL", "Total/HDL", "Atherogenic",
                "lipoprotein", "apolipoprotein",
            ],
            weight=4.0,
            category="strong_keyword",
        ),
    ],

    supporting_keyword_groups=[
        SignalGroup(
            patterns=["mg/dL", "mmol/L", "fasting"],
            weight=1.5,
            category="supporting_keyword",
        ),
    ],

    exclusion_patterns=[
        "ejection fraction", "haemoglobin", "bilirubin", "TSH", "creatinine",
    ],

    min_score_threshold=8.0,
)


LIVER_FUNCTION = ReportSignature(
    canonical_name="liver_function_test",
    aliases=["LFT", "Liver Function Test", "Hepatic Panel", "Liver Panel"],

    title_patterns=[
        "LIVER FUNCTION TEST",
        "LIVER FUNCTION TESTS",
        "LFT",
        "HEPATIC PANEL",
        "LIVER PANEL",
        "LIVER PROFILE",
    ],

    section_patterns=[
        "LIVER FUNCTION",
        "HEPATIC",
        "BILIRUBIN",
        "LIVER ENZYMES",
    ],

    table_patterns=[
        "LIVER FUNCTION",
        "LFT",
        "BILIRUBIN",
        "LIVER PANEL",
    ],

    measurement_patterns=[
        "Total Bilirubin", "Direct Bilirubin", "Indirect Bilirubin",
        "SGPT", "ALT", "Alanine Aminotransferase",
        "SGOT", "AST", "Aspartate Aminotransferase",
        "Alkaline Phosphatase", "ALP",
        "GGT", "Gamma GT", "Gamma-Glutamyl Transferase",
        "Total Protein",
        "Albumin", "Globulin",
        "A/G Ratio",
        "Prothrombin Time", "PT",
        "LDH",
    ],

    strong_keyword_groups=[
        SignalGroup(
            patterns=[
                "Bilirubin", "SGPT", "ALT", "SGOT", "AST",
                "Alkaline Phosphatase", "ALP", "GGT",
            ],
            weight=5.0,
            category="strong_keyword",
        ),
        SignalGroup(
            patterns=[
                "Albumin", "Globulin", "Total Protein", "A/G Ratio",
                "Prothrombin", "hepatic",
            ],
            weight=4.0,
            category="strong_keyword",
        ),
    ],

    supporting_keyword_groups=[
        SignalGroup(
            patterns=["IU/L", "U/L", "g/dL", "liver"],
            weight=1.5,
            category="supporting_keyword",
        ),
    ],

    exclusion_patterns=[
        "ejection fraction", "haemoglobin", "TSH", "creatinine", "cholesterol",
    ],

    min_score_threshold=8.0,
)


RENAL_FUNCTION = ReportSignature(
    canonical_name="renal_function_test",
    aliases=["RFT", "KFT", "Kidney Function Test", "Renal Function Test", "Renal Panel"],

    title_patterns=[
        "RENAL FUNCTION TEST",
        "RENAL FUNCTION TESTS",
        "KIDNEY FUNCTION TEST",
        "RFT",
        "KFT",
        "RENAL PANEL",
        "KIDNEY PANEL",
        "RENAL PROFILE",
    ],

    section_patterns=[
        "RENAL FUNCTION",
        "KIDNEY FUNCTION",
        "ELECTROLYTES",
        "RENAL PANEL",
    ],

    table_patterns=[
        "RENAL FUNCTION",
        "KIDNEY FUNCTION",
        "ELECTROLYTES",
        "RFT",
        "KFT",
    ],

    measurement_patterns=[
        "Creatinine", "Serum Creatinine",
        "Blood Urea Nitrogen", "BUN", "Urea", "Blood Urea",
        "eGFR", "GFR", "Glomerular Filtration Rate",
        "Uric Acid",
        "Sodium", "Na+",
        "Potassium", "K+",
        "Chloride", "Cl-",
        "Bicarbonate", "HCO3",
        "Phosphorus", "Calcium",
    ],

    strong_keyword_groups=[
        SignalGroup(
            patterns=[
                "Creatinine", "Urea", "BUN",
                "eGFR", "GFR",
                "Uric Acid",
            ],
            weight=5.0,
            category="strong_keyword",
        ),
        SignalGroup(
            patterns=[
                "Sodium", "Potassium", "Chloride", "Bicarbonate",
                "Electrolytes",
            ],
            weight=3.5,
            category="strong_keyword",
        ),
    ],

    supporting_keyword_groups=[
        SignalGroup(
            patterns=["mg/dL", "mmol/L", "mEq/L", "renal", "kidney"],
            weight=1.5,
            category="supporting_keyword",
        ),
    ],

    exclusion_patterns=[
        "ejection fraction", "haemoglobin", "bilirubin", "TSH", "cholesterol",
    ],

    min_score_threshold=8.0,
)


THYROID_FUNCTION = ReportSignature(
    canonical_name="thyroid_function_test",
    aliases=["TFT", "Thyroid Profile", "Thyroid Function Test"],

    title_patterns=[
        "THYROID FUNCTION TEST",
        "THYROID FUNCTION TESTS",
        "THYROID PROFILE",
        "TFT",
        "THYROID PANEL",
    ],

    section_patterns=[
        "THYROID FUNCTION",
        "THYROID PANEL",
        "THYROID PROFILE",
    ],

    table_patterns=[
        "THYROID FUNCTION",
        "THYROID PANEL",
        "THYROID PROFILE",
        "TFT",
    ],

    measurement_patterns=[
        "TSH", "Thyroid Stimulating Hormone",
        "Free T3", "fT3", "Triiodothyronine",
        "Free T4", "fT4", "Thyroxine",
        "Total T3",
        "Total T4",
        "Anti-TPO", "Anti-Thyroglobulin", "TPO Antibody",
        "Thyroglobulin",
    ],

    strong_keyword_groups=[
        SignalGroup(
            patterns=[
                "TSH", "Thyroid Stimulating Hormone",
                "T3", "T4", "fT3", "fT4",
                "Thyroxine", "Triiodothyronine",
            ],
            weight=5.0,
            category="strong_keyword",
        ),
        SignalGroup(
            patterns=[
                "Anti-TPO", "TPO", "Thyroglobulin",
                "hypothyroid", "hyperthyroid",
            ],
            weight=4.0,
            category="strong_keyword",
        ),
    ],

    supporting_keyword_groups=[
        SignalGroup(
            patterns=["mIU/L", "uIU/mL", "pmol/L", "thyroid"],
            weight=1.5,
            category="supporting_keyword",
        ),
    ],

    exclusion_patterns=[
        "ejection fraction", "haemoglobin", "bilirubin", "creatinine", "cholesterol",
    ],

    min_score_threshold=8.0,
)


ECG = ReportSignature(
    canonical_name="ecg",
    aliases=["ECG", "EKG", "Electrocardiogram", "Electrocardiography"],

    title_patterns=[
        "ELECTROCARDIOGRAM",
        "ELECTROCARDIOGRAPHY",
        "ECG REPORT",
        "EKG REPORT",
        "12-LEAD ECG",
        "12 LEAD ECG",
        "ECG",
        "EKG",
    ],

    section_patterns=[
        "ECG FINDINGS",
        "ECG INTERPRETATION",
        "RHYTHM",
        "CARDIAC RHYTHM",
        "INTERVALS",
        "ECG",
        "EKG",
    ],

    table_patterns=[
        "ECG",
        "INTERVALS",
        "RHYTHM",
        "P-WAVE", "QRS", "T-WAVE",
    ],

    measurement_patterns=[
        "Heart Rate", "Pulse Rate",
        "PR Interval", "PR",
        "QRS Duration", "QRS",
        "QT Interval", "QTc", "QT",
        "RR Interval",
        "P Wave Duration",
        "QRS Axis",
        "ST Segment",
    ],

    strong_keyword_groups=[
        SignalGroup(
            patterns=[
                "PR Interval", "QRS", "QT Interval", "QTc",
                "ST segment", "ST elevation", "ST depression",
                "sinus rhythm", "atrial fibrillation",
                "bundle branch block", "LBBB", "RBBB",
            ],
            weight=5.0,
            category="strong_keyword",
        ),
        SignalGroup(
            patterns=[
                "heart rate", "rhythm", "P wave", "T wave",
                "ventricular", "atrial",
                "tachycardia", "bradycardia",
            ],
            weight=3.5,
            category="strong_keyword",
        ),
    ],

    supporting_keyword_groups=[
        SignalGroup(
            patterns=["ms", "msec", "bpm", "lead", "electrocardiogram"],
            weight=1.5,
            category="supporting_keyword",
        ),
    ],

    exclusion_patterns=[
        "haemoglobin", "bilirubin", "TSH", "creatinine", "cholesterol",
        "ejection fraction",   # ECG does not report EF (echo does)
    ],

    min_score_threshold=8.0,
)


RADIOLOGY = ReportSignature(
    canonical_name="radiology",
    aliases=["X-Ray", "CT Scan", "MRI", "Ultrasound", "Radiology Report",
             "Imaging Report"],

    title_patterns=[
        "RADIOLOGY REPORT",
        "X-RAY REPORT",
        "CT REPORT",
        "MRI REPORT",
        "ULTRASOUND REPORT",
        "IMAGING REPORT",
        "RADIOLOGICAL REPORT",
        "USG REPORT",
        "COMPUTED TOMOGRAPHY",
        "MAGNETIC RESONANCE IMAGING",
    ],

    section_patterns=[
        "CLINICAL INDICATION",
        "TECHNIQUE",
        "FINDINGS",
        "IMPRESSION",
        "RECOMMENDATION",
        "RADIOLOGICAL FINDINGS",
        "CT FINDINGS",
        "MRI FINDINGS",
        "X-RAY FINDINGS",
    ],

    table_patterns=[],   # Radiology reports are typically narrative, not tabular.

    measurement_patterns=[
        "size", "dimension", "diameter",
        "density", "attenuation",
        "Hounsfield", "HU",
    ],

    strong_keyword_groups=[
        SignalGroup(
            patterns=[
                "radiograph", "X-ray", "CT scan", "MRI",
                "ultrasound", "sonography", "USG",
                "opacity", "consolidation", "effusion",
                "lytic", "sclerotic",
                "Hounsfield",
            ],
            weight=5.0,
            category="strong_keyword",
        ),
        SignalGroup(
            patterns=[
                "atelectasis", "pneumonia", "fracture",
                "calcification", "nodule", "mass",
                "lymph node", "soft tissue",
                "contrast", "enhancement",
            ],
            weight=4.0,
            category="strong_keyword",
        ),
    ],

    supporting_keyword_groups=[
        SignalGroup(
            patterns=[
                "radiology", "radiologist", "imaging",
                "bilateral", "unilateral", "anterior", "posterior",
                "right", "left", "superior", "inferior",
            ],
            weight=1.5,
            category="supporting_keyword",
        ),
    ],

    exclusion_patterns=[
        "ejection fraction", "haemoglobin", "bilirubin", "TSH", "creatinine",
    ],

    min_score_threshold=8.0,
)


# ---------------------------------------------------------------------------
# Registry — all signatures in priority order
# ---------------------------------------------------------------------------
# The classifier iterates this list.  Order does NOT affect scoring but
# determines tie-break ordering for the "alternatives" list.

ALL_SIGNATURES: list[ReportSignature] = [
    ECHOCARDIOGRAPHY,
    CBC,
    LIPID_PROFILE,
    LIVER_FUNCTION,
    RENAL_FUNCTION,
    THYROID_FUNCTION,
    ECG,
    RADIOLOGY,
]
