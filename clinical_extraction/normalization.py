"""
clinical_extraction/normalization.py

Configurable terminology normalization layer.

Maps medical abbreviations and clinical shorthand to standard canonical terms.
The original text is ALWAYS preserved; normalized forms are added as separate
fields. If no confident mapping exists, the normalized field is left as None.
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Configurable dictionary mappings by report type or domain
# ---------------------------------------------------------------------------

ECHOCARDIOGRAPHY_TERMINOLOGY: dict[str, str] = {
    # Acronyms & Short forms
    "ef": "Ejection Fraction",
    "ejection fraction": "Ejection Fraction",
    "fs": "Fractional Shortening",
    "fractional shortening": "Fractional Shortening",
    "lvh": "Left Ventricular Hypertrophy",
    "left ventricular hypertrophy": "Left Ventricular Hypertrophy",
    "conc lvh": "Concentric Left Ventricular Hypertrophy",
    "concentric lvh": "Concentric Left Ventricular Hypertrophy",
    "eccentric lvh": "Eccentric Left Ventricular Hypertrophy",
    "rwma": "Regional Wall Motion Abnormality",
    "regional wall motion abnormality": "Regional Wall Motion Abnormality",
    "no rwma": "Regional Wall Motion Abnormality",
    "lvdd": "Left Ventricular Diastolic Dysfunction",
    "left ventricular diastolic dysfunction": "Left Ventricular Diastolic Dysfunction",
    "grade 1 lvdd": "Grade 1 Left Ventricular Diastolic Dysfunction",
    "grade 2 lvdd": "Grade 2 Left Ventricular Diastolic Dysfunction",
    "grade 3 lvdd": "Grade 3 Left Ventricular Diastolic Dysfunction",
    "tr": "Tricuspid Regurgitation",
    "mild tr": "Mild Tricuspid Regurgitation",
    "moderate tr": "Moderate Tricuspid Regurgitation",
    "severe tr": "Severe Tricuspid Regurgitation",
    "tricuspid regurgitation": "Tricuspid Regurgitation",
    "mr": "Mitral Regurgitation",
    "mild mr": "Mild Mitral Regurgitation",
    "moderate mr": "Moderate Mitral Regurgitation",
    "severe mr": "Severe Mitral Regurgitation",
    "mitral regurgitation": "Mitral Regurgitation",
    "ar": "Aortic Regurgitation",
    "mild ar": "Mild Aortic Regurgitation",
    "moderate ar": "Moderate Aortic Regurgitation",
    "severe ar": "Severe Aortic Regurgitation",
    "aortic regurgitation": "Aortic Regurgitation",
    "no aortic regurgitation": "Aortic Regurgitation",
    "pr": "Pulmonary Regurgitation",
    "mild pr": "Mild Pulmonary Regurgitation",
    "pulmonary regurgitation": "Pulmonary Regurgitation",
    "no pulmonary regurgitation": "Pulmonary Regurgitation",
    "no pulmonary regurgitation present": "Pulmonary Regurgitation",
    "as": "Aortic Stenosis",
    "ms": "Mitral Stenosis",
    "ps": "Pulmonary Stenosis",
    "ts": "Tricuspid Stenosis",
    "pasp": "Pulmonary Artery Systolic Pressure",
    "pulmonary artery systolic pressure": "Pulmonary Artery Systolic Pressure",
    "pah": "Pulmonary Arterial Hypertension",
    "ph": "Pulmonary Hypertension",
    # Anatomy abbreviations
    "lv": "Left Ventricle",
    "left ventricle": "Left Ventricle",
    "rv": "Right Ventricle",
    "right ventricle": "Right Ventricle",
    "la": "Left Atrium",
    "left atrium": "Left Atrium",
    "ra": "Right Atrium",
    "right atrium": "Right Atrium",
    "ias": "Interatrial Septum",
    "interatrial septum": "Interatrial Septum",
    "ivs": "Interventricular Septum",
    "interventricular septum": "Interventricular Septum",
    "lvot": "Left Ventricular Outflow Tract",
    "left ventricular outflow tract": "Left Ventricular Outflow Tract",
    "rvot": "Right Ventricular Outflow Tract",
    "aortic root": "Aortic Root",
    "aortic root diameter": "Aortic Root Diameter",
    "left atrial diameter": "Left Atrial Diameter",
    "left ventricular ed dimension": "Left Ventricular End-Diastolic Dimension",
    "left ventricular es dimension": "Left Ventricular End-Systolic Dimension",
    "lvedd": "Left Ventricular End-Diastolic Dimension",
    "lvesd": "Left Ventricular End-Systolic Dimension",
    "inter vent. septum thickness d": "Interventricular Septum Thickness in Diastole",
    "ivsd": "Interventricular Septum Thickness in Diastole",
    "lvposterior wall thickness d": "Left Ventricular Posterior Wall Thickness in Diastole",
    "lvpwd": "Left Ventricular Posterior Wall Thickness in Diastole",
    "mitral valve": "Mitral Valve",
    "tricuspid valve": "Tricuspid Valve",
    "aortic valve": "Aortic Valve",
    "pulmonary valve": "Pulmonary Valve",
    "pulmonic valve": "Pulmonary Valve",
    "pericardium": "Pericardium",
    "pulmonary artery": "Pulmonary Artery",
    # Clinical concepts
    "effusion": "Pericardial Effusion",
    "pericardial effusion": "Pericardial Effusion",
    "vegetation": "Vegetation",
    "vegetations": "Vegetation",
    "clot": "Thrombus",
    "thrombus": "Thrombus",
    "mass": "Cardiac Mass",
    "normal lv function": "Normal Left Ventricular Function",
    "normal rv function": "Normal Right Ventricular Function",
    "lv function": "Left Ventricular Function",
    "rv function": "Right Ventricular Function",
    "aortic velocity": "Aortic Velocity",
    "pulmonary velocity": "Pulmonary Velocity",
}

CBC_TERMINOLOGY: dict[str, str] = {
    "hb": "Hemoglobin",
    "hgb": "Hemoglobin",
    "haemoglobin": "Hemoglobin",
    "hemoglobin": "Hemoglobin",
    "wbc": "White Blood Cell Count",
    "tlc": "Total Leukocyte Count",
    "rbc": "Red Blood Cell Count",
    "plt": "Platelet Count",
    "platelets": "Platelet Count",
    "platelet count": "Platelet Count",
    "pcv": "Packed Cell Volume",
    "hct": "Hematocrit",
    "hematocrit": "Hematocrit",
    "mcv": "Mean Corpuscular Volume",
    "mch": "Mean Corpuscular Hemoglobin",
    "mchc": "Mean Corpuscular Hemoglobin Concentration",
    "rdw": "Red Cell Distribution Width",
    "rdw-cv": "Red Cell Distribution Width - CV",
    "neutrophils": "Neutrophils",
    "lymphocytes": "Lymphocytes",
    "monocytes": "Monocytes",
    "eosinophils": "Eosinophils",
    "basophils": "Basophils",
    "esr": "Erythrocyte Sedimentation Rate",
}

LIPID_TERMINOLOGY: dict[str, str] = {
    "tc": "Total Cholesterol",
    "total cholesterol": "Total Cholesterol",
    "cholesterol": "Total Cholesterol",
    "tg": "Triglycerides",
    "triglycerides": "Triglycerides",
    "triglyceride": "Triglycerides",
    "hdl": "High-Density Lipoprotein Cholesterol",
    "hdl-c": "High-Density Lipoprotein Cholesterol",
    "hdl cholesterol": "High-Density Lipoprotein Cholesterol",
    "ldl": "Low-Density Lipoprotein Cholesterol",
    "ldl-c": "Low-Density Lipoprotein Cholesterol",
    "ldl cholesterol": "Low-Density Lipoprotein Cholesterol",
    "vldl": "Very Low-Density Lipoprotein Cholesterol",
    "vldl-c": "Very Low-Density Lipoprotein Cholesterol",
    "vldl cholesterol": "Very Low-Density Lipoprotein Cholesterol",
    "non-hdl": "Non-HDL Cholesterol",
    "non-hdl cholesterol": "Non-HDL Cholesterol",
}

LIVER_TERMINOLOGY: dict[str, str] = {
    "alt": "Alanine Aminotransferase",
    "sgpt": "Alanine Aminotransferase",
    "ast": "Aspartate Aminotransferase",
    "sgot": "Aspartate Aminotransferase",
    "alp": "Alkaline Phosphatase",
    "alkaline phosphatase": "Alkaline Phosphatase",
    "ggt": "Gamma-Glutamyl Transferase",
    "gamma gt": "Gamma-Glutamyl Transferase",
    "total bilirubin": "Total Bilirubin",
    "direct bilirubin": "Direct Bilirubin",
    "indirect bilirubin": "Indirect Bilirubin",
    "total protein": "Total Protein",
    "albumin": "Albumin",
    "globulin": "Globulin",
    "a/g ratio": "Albumin/Globulin Ratio",
}

RENAL_TERMINOLOGY: dict[str, str] = {
    "creatinine": "Serum Creatinine",
    "serum creatinine": "Serum Creatinine",
    "bun": "Blood Urea Nitrogen",
    "blood urea nitrogen": "Blood Urea Nitrogen",
    "urea": "Blood Urea",
    "blood urea": "Blood Urea",
    "egfr": "Estimated Glomerular Filtration Rate",
    "gfr": "Glomerular Filtration Rate",
    "uric acid": "Uric Acid",
    "sodium": "Sodium",
    "potassium": "Potassium",
    "chloride": "Chloride",
}

THYROID_TERMINOLOGY: dict[str, str] = {
    "tsh": "Thyroid Stimulating Hormone",
    "t3": "Triiodothyronine",
    "total t3": "Total Triiodothyronine",
    "ft3": "Free Triiodothyronine",
    "free t3": "Free Triiodothyronine",
    "t4": "Thyroxine",
    "total t4": "Total Thyroxine",
    "ft4": "Free Thyroxine",
    "free t4": "Free Thyroxine",
    "anti-tpo": "Anti-Thyroid Peroxidase Antibody",
}

ECG_TERMINOLOGY: dict[str, str] = {
    "nsr": "Normal Sinus Rhythm",
    "sinus rhythm": "Normal Sinus Rhythm",
    "af": "Atrial Fibrillation",
    "afib": "Atrial Fibrillation",
    "lbbb": "Left Bundle Branch Block",
    "rbbb": "Right Bundle Branch Block",
    "pvc": "Premature Ventricular Contraction",
    "pac": "Premature Atrial Contraction",
    "stemi": "ST-Elevation Myocardial Infarction",
    "nstemi": "Non-ST-Elevation Myocardial Infarction",
    "hr": "Heart Rate",
    "heart rate": "Heart Rate",
    "pr interval": "PR Interval",
    "qrs duration": "QRS Duration",
    "qtc": "Corrected QT Interval",
}

RADIOLOGY_TERMINOLOGY: dict[str, str] = {
    "cxr": "Chest X-Ray",
    "ct": "Computed Tomography",
    "mri": "Magnetic Resonance Imaging",
    "usg": "Ultrasonography",
    "consolidation": "Pulmonary Consolidation",
    "atelectasis": "Atelectasis",
    "pneumothorax": "Pneumothorax",
    "pleural effusion": "Pleural Effusion",
    "cardiomegaly": "Cardiomegaly",
}

# Aggregate registry indexed by report type
REPORT_TYPE_REGISTRY: dict[str, dict[str, str]] = {
    "echocardiography": ECHOCARDIOGRAPHY_TERMINOLOGY,
    "cbc": CBC_TERMINOLOGY,
    "complete_blood_count": CBC_TERMINOLOGY,
    "lipid_profile": LIPID_TERMINOLOGY,
    "liver_function_test": LIVER_TERMINOLOGY,
    "renal_function_test": RENAL_TERMINOLOGY,
    "thyroid_function_test": THYROID_TERMINOLOGY,
    "ecg": ECG_TERMINOLOGY,
    "radiology": RADIOLOGY_TERMINOLOGY,
}

# Universal fallbacks
UNIVERSAL_TERMINOLOGY: dict[str, str] = {}
for _d in (
    ECHOCARDIOGRAPHY_TERMINOLOGY,
    CBC_TERMINOLOGY,
    LIPID_TERMINOLOGY,
    LIVER_TERMINOLOGY,
    RENAL_TERMINOLOGY,
    THYROID_TERMINOLOGY,
    ECG_TERMINOLOGY,
    RADIOLOGY_TERMINOLOGY,
):
    UNIVERSAL_TERMINOLOGY.update(_d)


# ---------------------------------------------------------------------------
# Normalization functions
# ---------------------------------------------------------------------------


def normalize_term(
    term: str,
    report_type: Optional[str] = None,
) -> Optional[str]:
    """
    Look up the normalized representation of a clinical term.

    Parameters
    ----------
    term:
        The term as extracted from source text (e.g. 'LVH', 'Mild TR').
    report_type:
        Optional report type for context-specific dictionary preference.

    Returns
    -------
    Optional[str]
        Canonical medical term if a confident match exists, else None.
    """
    if not term:
        return None

    # Clean punctuation, strip whitespace, lowercase
    cleaned = re.sub(r"[*_`#:]", "", term).strip().lower()

    # 1. Try report-type specific dictionary
    if report_type and report_type in REPORT_TYPE_REGISTRY:
        domain_dict = REPORT_TYPE_REGISTRY[report_type]
        if cleaned in domain_dict:
            return domain_dict[cleaned]

    # 2. Try universal dictionary
    if cleaned in UNIVERSAL_TERMINOLOGY:
        return UNIVERSAL_TERMINOLOGY[cleaned]

    # 3. Strip leading qualifier (e.g. "mild tr" -> lookup "tr" -> prepend "Mild ")
    # or handle common prefixes
    for prefix in ("mild ", "moderate ", "severe ", "conc ", "concentric ", "grade 1 ", "grade 2 ", "grade 3 "):
        if cleaned.startswith(prefix):
            core = cleaned[len(prefix):].strip()
            # Try core in domain or universal
            norm_core = None
            if report_type and report_type in REPORT_TYPE_REGISTRY:
                norm_core = REPORT_TYPE_REGISTRY[report_type].get(core)
            if not norm_core:
                norm_core = UNIVERSAL_TERMINOLOGY.get(core)

            if norm_core:
                prefix_title = prefix.strip().title()
                return f"{prefix_title} {norm_core}"

    return None
