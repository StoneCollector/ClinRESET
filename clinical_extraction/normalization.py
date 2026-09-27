"""
clinical_extraction/normalization.py

Configurable terminology normalization layer.

Maps medical abbreviations and clinical shorthand to standard canonical terms.
The original text is ALWAYS preserved; normalized forms are added as separate
fields. If no confident mapping exists, the normalized field is left as None.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from clinical_extraction.terminology.models import (
    AmbiguityStatus,
    ResolutionContext,
    ResolutionResult,
)
from clinical_extraction.terminology.resolver import get_resolver


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
    # Additional Findings & Valvular Observations
    "no effusion": "Pericardial Effusion",
    "no la/lv clot": "Thrombus",
    "la/lv clot": "Thrombus",
    "no clot": "Thrombus",
    "no gradient across lvot": "Left Ventricular Outflow Tract Gradient",
    "gradient across lvot": "Left Ventricular Outflow Tract Gradient",
    "ias/ivs intact": "Intact Interatrial and Interventricular Septa",
    "mitral valve: normal": "Normal Mitral Valve",
    "mitral valve normal": "Normal Mitral Valve",
    "pulmonary valve: normal": "Normal Pulmonary Valve",
    "pulmonary valve normal": "Normal Pulmonary Valve",
    "normal, opens well": "Normal Valve Motion",
    "opens well": "Normal Valve Motion",
    "no prolapse": "Valve Prolapse",
    "prolapse": "Valve Prolapse",
    "normal 'ef' slope": "Normal Pulmonary Valve EF Slope",
    "normal ef slope": "Normal Pulmonary Valve EF Slope",
    "ef slope": "Pulmonary Valve EF Slope",
    "'ef' slope": "Pulmonary Valve EF Slope",
    "normal 'a' wave": "Normal Pulmonary Valve A Wave",
    "normal a wave": "Normal Pulmonary Valve A Wave",
    "a wave": "Pulmonary Valve A Wave",
    "'a' wave": "Pulmonary Valve A Wave",
    "no midsystolic notch": "Midsystolic Notch",
    "midsystolic notch": "Midsystolic Notch",
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


def resolve_term(
    term: str,
    context: Optional[ResolutionContext] = None,
    report_type: Optional[str] = None,
    section_title: Optional[str] = None,
    nearby_text: Optional[str] = None,
    anatomy_context: Optional[list[str]] = None,
    measurement_context: Optional[list[str]] = None,
    extracted_entities: Optional[list[Any]] = None,
    relationships: Optional[list[Any]] = None,
) -> ResolutionResult:
    """
    Resolve and normalize a clinical surface form with full contextual disambiguation.

    Uses the 8-level contextual resolution hierarchy:
    1. report_type
    2. section title
    3. nearby terminology
    4. anatomy context
    5. measurement context
    6. existing Phase 3 extracted entities
    7. existing relationships
    8. domain-specific terminology mappings
    """
    if not term:
        return ResolutionResult(
            text=term or "",
            normalized=None,
            ambiguity=False,
            ambiguity_status=AmbiguityStatus.NOT_APPLICABLE,
            provenance="empty_input",
        )

    # Clean formatting and normalize quotation marks
    cleaned = term.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    cleaned = re.sub(r"[*_`#:]", "", cleaned)
    cleaned = " ".join(cleaned.split()).strip()

    # Build context
    if context is None:
        domain_mappings = REPORT_TYPE_REGISTRY.get(report_type) if report_type else None
        context = ResolutionContext(
            report_type=report_type,
            section_title=section_title,
            nearby_text=nearby_text,
            anatomy_context=anatomy_context or [],
            measurement_context=measurement_context or [],
            extracted_entities=extracted_entities or [],
            relationships=relationships or [],
            domain_mappings=domain_mappings,
        )
    else:
        if report_type and not context.report_type:
            context.report_type = report_type
        if section_title and not context.section_title:
            context.section_title = section_title
        if nearby_text and not context.nearby_text:
            context.nearby_text = nearby_text
        if not context.domain_mappings and context.report_type:
            context.domain_mappings = REPORT_TYPE_REGISTRY.get(context.report_type)

    resolver = get_resolver()

    # Prefix expansion mappings
    prefix_expansions = {
        "mild ": "Mild",
        "moderate ": "Moderate",
        "severe ": "Severe",
        "conc ": "Concentric",
        "concentric ": "Concentric",
        "eccentric ": "Eccentric",
        "grade 1 ": "Grade 1",
        "grade 2 ": "Grade 2",
        "grade 3 ": "Grade 3",
        "grade i ": "Grade 1",
        "grade ii ": "Grade 2",
        "grade iii ": "Grade 3",
    }

    cleaned_lower = cleaned.lower()
    cleaned_no_quotes = cleaned_lower.replace("'", "").replace('"', '')

    # 1. Direct match in domain dictionary if report_type specified (Requirement 11)
    if context.report_type and context.domain_mappings:
        dict_key = None
        if cleaned_lower in context.domain_mappings:
            dict_key = cleaned_lower
        elif cleaned_no_quotes in context.domain_mappings:
            dict_key = cleaned_no_quotes

        if dict_key:
            mapped_val = context.domain_mappings[dict_key]
            rec = resolver.corpus.lookup(dict_key)
            cands = [c.term for c in rec.candidates] if rec else [mapped_val]
            safety = None
            if rec and any(c.is_safety_warning for c in rec.candidates):
                safety = f"Joint Commission safety warning for '{term}'"
            return ResolutionResult(
                text=term,
                normalized=mapped_val,
                normalization_source="domain_specific_mappings",
                ambiguity=False,
                ambiguity_status=AmbiguityStatus.RESOLVED,
                candidates=cands,
                domain=context.report_type,
                safety_warning=safety,
                provenance="report_type_registry_match",
            )

    # 2. Check common clinical prefixes (e.g. "mild tr", "moderate mr", "grade 1 lvdd", "conc lvh")
    for prefix, prefix_title in prefix_expansions.items():
        if cleaned_lower.startswith(prefix):
            core = cleaned[len(prefix):].strip()
            core_res = resolver.resolve(core, context=context)
            if core_res.ambiguity_status == AmbiguityStatus.RESOLVED and core_res.normalized:
                return ResolutionResult(
                    text=term,
                    normalized=f"{prefix_title} {core_res.normalized}",
                    normalization_source=core_res.normalization_source,
                    ambiguity=False,
                    ambiguity_status=AmbiguityStatus.RESOLVED,
                    candidates=[f"{prefix_title} {c}" for c in core_res.candidates],
                    domain=core_res.domain,
                    safety_warning=core_res.safety_warning,
                    provenance=f"qualified_term: {core_res.provenance}",
                )
            elif core_res.ambiguity_status == AmbiguityStatus.AMBIGUOUS:
                return ResolutionResult(
                    text=term,
                    normalized=None,
                    normalization_source=core_res.normalization_source,
                    ambiguity=True,
                    ambiguity_status=AmbiguityStatus.AMBIGUOUS,
                    candidates=[f"{prefix_title} {c}" for c in core_res.candidates],
                    domain=core_res.domain,
                    safety_warning=core_res.safety_warning,
                    provenance=f"qualified_ambiguous_term: {core_res.provenance}",
                )

    # 3. Use hierarchical terminology corpus resolver
    corpus_res = resolver.resolve(term, context=context)
    if corpus_res.ambiguity_status != AmbiguityStatus.UNKNOWN:
        corpus_res.text = term
        return corpus_res

    # 4. Fallback: check universal dictionary for multi-word phrases not in corpus
    fb_key = None
    if cleaned_lower in UNIVERSAL_TERMINOLOGY:
        fb_key = cleaned_lower
    elif cleaned_no_quotes in UNIVERSAL_TERMINOLOGY:
        fb_key = cleaned_no_quotes

    if fb_key:
        mapped_val = UNIVERSAL_TERMINOLOGY[fb_key]
        return ResolutionResult(
            text=term,
            normalized=mapped_val,
            normalization_source="universal_dictionary",
            ambiguity=False,
            ambiguity_status=AmbiguityStatus.RESOLVED,
            candidates=[mapped_val],
            provenance="universal_dictionary_match",
        )

    corpus_res.text = term
    return corpus_res


def normalize_term(
    term: str,
    report_type: Optional[str] = None,
) -> Optional[str]:
    """
    Look up the normalized representation of a clinical term.

    Maintains backward compatibility with Phase 3 callers.
    Returns canonical string if resolved, or None if ambiguous, unknown, or not applicable.
    """
    if not term:
        return None

    res = resolve_term(term, report_type=report_type)
    if res.ambiguity_status == AmbiguityStatus.RESOLVED:
        return res.normalized
    return None
