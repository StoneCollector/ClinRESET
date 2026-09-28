"""
clinical_explanation/knowledge_base.py

Deterministic explanation knowledge base for echocardiography concepts.

Contains standardized, patient-accessible definitions explaining WHAT each clinical
term or measurement represents without diagnostic claims, risk stratification,
or prognostic interpretations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KnowledgeBaseEntry:
    """A deterministic explanation entry for a clinical concept."""

    concept: str
    definition: str
    category: str
    anatomy: str
    what_it_measures: Optional[str] = None
    present_description: Optional[str] = None
    absent_description: Optional[str] = None
    normal_description: Optional[str] = None


ECHO_KNOWLEDGE_BASE: dict[str, KnowledgeBaseEntry] = {
    # -----------------------------------------------------------------------
    # 1. FUNCTION CONCEPTS
    # -----------------------------------------------------------------------
    "ejection fraction": KnowledgeBaseEntry(
        concept="Ejection Fraction",
        definition=(
            "Ejection fraction is a measurement of the percentage of blood pumped out "
            "of the left ventricle with each contraction."
        ),
        category="FUNCTION",
        anatomy="Left Ventricle",
        what_it_measures="the percentage of blood emptied from the left ventricle during each heartbeat",
    ),
    "fractional shortening": KnowledgeBaseEntry(
        concept="Fractional Shortening",
        definition=(
            "Fractional shortening is an ultrasound measurement of the percentage change in "
            "the diameter of the left ventricle between its relaxed state and its contracted state."
        ),
        category="FUNCTION",
        anatomy="Left Ventricle",
        what_it_measures="the change in left ventricular diameter between diastole and systole",
    ),
    "normal left ventricular function": KnowledgeBaseEntry(
        concept="Normal Left Ventricular Function",
        definition=(
            "Left ventricular function refers to how effectively the heart's main pumping chamber "
            "(the left ventricle) contracts and pumps blood throughout the body."
        ),
        category="FUNCTION",
        anatomy="Left Ventricle",
        normal_description="Left ventricular pumping function is described as normal.",
    ),
    "left ventricular function": KnowledgeBaseEntry(
        concept="Left Ventricular Function",
        definition=(
            "Left ventricular function refers to the overall contraction and pumping capacity "
            "of the heart's main pumping chamber (the left ventricle)."
        ),
        category="FUNCTION",
        anatomy="Left Ventricle",
        normal_description="Left ventricular function is described as normal.",
    ),
    "normal right ventricular function": KnowledgeBaseEntry(
        concept="Normal Right Ventricular Function",
        definition=(
            "Right ventricular function refers to the ability of the right lower chamber "
            "(the right ventricle) to pump blood forward into the pulmonary circulation toward the lungs."
        ),
        category="FUNCTION",
        anatomy="Right Ventricle",
        normal_description="Right ventricular pumping function is described as normal.",
    ),
    "right ventricular function": KnowledgeBaseEntry(
        concept="Right Ventricular Function",
        definition=(
            "Right ventricular function refers to the ability of the right ventricle to pump "
            "blood into the pulmonary artery toward the lungs."
        ),
        category="FUNCTION",
        anatomy="Right Ventricle",
        normal_description="Right ventricular function is described as normal.",
    ),

    # -----------------------------------------------------------------------
    # 2. STRUCTURAL CONCEPTS
    # -----------------------------------------------------------------------
    "concentric left ventricular hypertrophy": KnowledgeBaseEntry(
        concept="Concentric Left Ventricular Hypertrophy",
        definition=(
            "Concentric left ventricular hypertrophy refers to a pattern where the muscular walls "
            "of the left ventricle are uniformly thickened around the chamber."
        ),
        category="STRUCTURAL_FINDING",
        anatomy="Left Ventricle",
        present_description="The report identifies a pattern of concentric left ventricular wall thickening.",
    ),
    "left ventricular hypertrophy": KnowledgeBaseEntry(
        concept="Left Ventricular Hypertrophy",
        definition=(
            "Left ventricular hypertrophy refers to an increase in the muscular wall thickness "
            "of the left ventricle, the heart's main pumping chamber."
        ),
        category="STRUCTURAL_FINDING",
        anatomy="Left Ventricle",
        present_description="The report identifies thickening of the left ventricular muscular walls.",
    ),
    "intact interatrial and interventricular septa": KnowledgeBaseEntry(
        concept="Intact Interatrial and Interventricular Septa",
        definition=(
            "The interatrial septum is the dividing wall between the two upper heart chambers (atria), "
            "and the interventricular septum is the dividing wall between the two lower chambers (ventricles). "
            "When described as intact, ultrasound imaging demonstrates continuous wall structures without openings between chambers."
        ),
        category="STRUCTURAL_FINDING",
        anatomy="Interatrial Septum, Interventricular Septum",
        normal_description="The dividing walls between the upper chambers and lower chambers are described as intact and continuous.",
    ),
    "interatrial septum": KnowledgeBaseEntry(
        concept="Interatrial Septum",
        definition=(
            "The interatrial septum is the wall of cardiac tissue that separates the right atrium "
            "from the left atrium."
        ),
        category="STRUCTURAL_FINDING",
        anatomy="Interatrial Septum",
        normal_description="The interatrial septum is intact.",
    ),
    "interventricular septum": KnowledgeBaseEntry(
        concept="Interventricular Septum",
        definition=(
            "The interventricular septum is the muscular wall of cardiac tissue that separates the "
            "right ventricle from the left ventricle."
        ),
        category="STRUCTURAL_FINDING",
        anatomy="Interventricular Septum",
        normal_description="The interventricular septum is intact.",
    ),

    # -----------------------------------------------------------------------
    # 3. WALL MOTION CONCEPTS
    # -----------------------------------------------------------------------
    "regional wall motion abnormality": KnowledgeBaseEntry(
        concept="Regional Wall Motion Abnormality",
        definition=(
            "A regional wall motion abnormality describes a condition where a specific segment or section "
            "of the heart wall does not contract or move in coordination with adjacent areas during pumping."
        ),
        category="WALL_MOTION",
        anatomy="Left Ventricle",
        absent_description="Regional wall motion abnormality: none was reported.",
        present_description="A regional wall motion abnormality was noted in the report.",
    ),

    # -----------------------------------------------------------------------
    # 4. DIASTOLIC FUNCTION CONCEPTS
    # -----------------------------------------------------------------------
    "left ventricular diastolic dysfunction": KnowledgeBaseEntry(
        concept="Left Ventricular Diastolic Dysfunction",
        definition=(
            "Left ventricular diastolic dysfunction refers to how the left ventricle relaxes and fills "
            "with blood during the resting phase between heartbeats (diastole)."
        ),
        category="DIASTOLIC_FUNCTION",
        anatomy="Left Ventricle",
        present_description="Left ventricular diastolic dysfunction is noted in the report.",
    ),
    "grade 1 left ventricular diastolic dysfunction": KnowledgeBaseEntry(
        concept="Grade 1 Left Ventricular Diastolic Dysfunction",
        definition=(
            "Left ventricular diastolic dysfunction describes how the heart muscle relaxes during the filling "
            "phase between contractions. Grade 1 corresponds to an impaired relaxation pattern observed on Doppler blood flow measurements."
        ),
        category="DIASTOLIC_FUNCTION",
        anatomy="Left Ventricle",
        present_description="The report identifies Grade 1 left ventricular diastolic dysfunction, characterized by an impaired relaxation filling pattern.",
    ),

    # -----------------------------------------------------------------------
    # 5. VALVULAR CONCEPTS
    # -----------------------------------------------------------------------
    "tricuspid regurgitation": KnowledgeBaseEntry(
        concept="Tricuspid Regurgitation",
        definition=(
            "Tricuspid regurgitation refers to backward leakage of blood across the tricuspid valve "
            "from the right ventricle into the right atrium during heart contraction."
        ),
        category="VALVULAR_FINDING",
        anatomy="Tricuspid Valve",
        absent_description="Tricuspid regurgitation: none was reported.",
        present_description="Tricuspid regurgitation is noted in the report.",
    ),
    "mild tricuspid regurgitation": KnowledgeBaseEntry(
        concept="Mild Tricuspid Regurgitation",
        definition=(
            "Tricuspid regurgitation refers to backward leakage of blood across the tricuspid valve "
            "from the right ventricle into the right atrium during contraction. The qualifier mild reflects the extent of the regurgitant jet observed on Doppler imaging."
        ),
        category="VALVULAR_FINDING",
        anatomy="Tricuspid Valve",
        present_description="The report describes mild tricuspid regurgitation.",
    ),
    "aortic regurgitation": KnowledgeBaseEntry(
        concept="Aortic Regurgitation",
        definition=(
            "Aortic regurgitation refers to backward leakage of blood through the aortic valve from the "
            "aorta back into the left ventricle during diastole, when the heart relaxes and fills."
        ),
        category="VALVULAR_FINDING",
        anatomy="Aortic Valve",
        absent_description="Aortic regurgitation: none was reported.",
        present_description="Aortic regurgitation is noted in the report.",
    ),
    "pulmonary regurgitation": KnowledgeBaseEntry(
        concept="Pulmonary Regurgitation",
        definition=(
            "Pulmonary regurgitation refers to backward flow of blood across the pulmonary valve from "
            "the pulmonary artery back into the right ventricle during diastole."
        ),
        category="VALVULAR_FINDING",
        anatomy="Pulmonary Valve",
        absent_description="Pulmonary regurgitation: none was reported.",
        present_description="Pulmonary regurgitation is noted in the report.",
    ),
    "normal mitral valve": KnowledgeBaseEntry(
        concept="Normal Mitral Valve",
        definition=(
            "The mitral valve controls blood flow between the left atrium and the left ventricle. "
            "When described as normal, the valve leaflets appear thin, mobile, and open and close without structural restriction."
        ),
        category="VALVULAR_FINDING",
        anatomy="Mitral Valve",
        normal_description="The mitral valve is described as normal.",
    ),
    "mitral valve": KnowledgeBaseEntry(
        concept="Mitral Valve",
        definition=(
            "The mitral valve is the cardiac valve located between the left atrium and left ventricle, "
            "ensuring one-way blood flow into the heart's main pumping chamber."
        ),
        category="VALVULAR_FINDING",
        anatomy="Mitral Valve",
        normal_description="The mitral valve structure is described as normal.",
    ),
    "valve prolapse": KnowledgeBaseEntry(
        concept="Valve Prolapse",
        definition=(
            "Valve prolapse describes a condition where one or more leaflets of a cardiac valve buckle or "
            "billow backward into the chamber behind the valve during contraction."
        ),
        category="VALVULAR_FINDING",
        anatomy="Tricuspid Valve",
        absent_description="Valve prolapse: none was reported.",
        present_description="Valve prolapse was observed on imaging.",
    ),
    "normal valve motion": KnowledgeBaseEntry(
        concept="Normal Valve Motion",
        definition=(
            "Normal valve motion indicates that the valve leaflets demonstrate full, unrestricted opening "
            "and complete coaptation (closure) during the cardiac cycle."
        ),
        category="VALVULAR_FINDING",
        anatomy="Aortic Valve",
        normal_description="Valve motion is described as normal and opening well.",
    ),
    "normal pulmonary valve": KnowledgeBaseEntry(
        concept="Normal Pulmonary Valve",
        definition=(
            "The pulmonary valve regulates blood flow from the right ventricle into the pulmonary artery. "
            "When described as normal, the valve leaflets appear mobile and open appropriately during ventricular ejection."
        ),
        category="VALVULAR_FINDING",
        anatomy="Pulmonary Valve",
        normal_description="The pulmonary valve is described as normal.",
    ),
    "pulmonary valve": KnowledgeBaseEntry(
        concept="Pulmonary Valve",
        definition=(
            "The pulmonary valve is located between the right ventricle and the pulmonary artery, "
            "opening to permit blood flow to the lungs."
        ),
        category="VALVULAR_FINDING",
        anatomy="Pulmonary Valve",
        normal_description="The pulmonary valve is described as normal.",
    ),
    "aortic valve": KnowledgeBaseEntry(
        concept="Aortic Valve",
        definition=(
            "The aortic valve is the exit valve between the left ventricle and the main body artery (aorta), "
            "opening to allow oxygen-rich blood to be distributed to the body."
        ),
        category="VALVULAR_FINDING",
        anatomy="Aortic Valve",
        normal_description="The aortic valve is described as normal.",
    ),
    "tricuspid valve": KnowledgeBaseEntry(
        concept="Tricuspid Valve",
        definition=(
            "The tricuspid valve is situated between the right atrium and the right ventricle, "
            "regulating venous blood flow into the right ventricle."
        ),
        category="VALVULAR_FINDING",
        anatomy="Tricuspid Valve",
        normal_description="The tricuspid valve is described as normal.",
    ),

    # -----------------------------------------------------------------------
    # 6. PRESSURE CONCEPTS
    # -----------------------------------------------------------------------
    "pulmonary artery systolic pressure": KnowledgeBaseEntry(
        concept="Pulmonary Artery Systolic Pressure",
        definition=(
            "Pulmonary artery systolic pressure (PASP) is an echocardiographic estimation of the peak blood pressure "
            "within the pulmonary artery, calculated using Doppler velocity measurements of tricuspid regurgitation flow."
        ),
        category="PRESSURE",
        anatomy="Pulmonary Artery",
        what_it_measures="the estimated peak systolic blood pressure in the pulmonary artery",
    ),

    # -----------------------------------------------------------------------
    # 7. DOPPLER CONCEPTS
    # -----------------------------------------------------------------------
    "aortic velocity": KnowledgeBaseEntry(
        concept="Aortic Velocity",
        definition=(
            "Aortic velocity is a Doppler ultrasound measurement of the peak speed of blood flowing across "
            "the aortic valve into the aorta during ventricular contraction."
        ),
        category="DOPPLER_MEASUREMENT",
        anatomy="Aorta",
        what_it_measures="the peak speed of forward blood flow through the aortic valve",
    ),
    "pulmonary velocity": KnowledgeBaseEntry(
        concept="Pulmonary Velocity",
        definition=(
            "Pulmonary velocity is a Doppler ultrasound measurement of the peak speed of blood moving across "
            "the pulmonary valve into the pulmonary artery during ventricular ejection."
        ),
        category="DOPPLER_MEASUREMENT",
        anatomy="Pulmonary Artery",
        what_it_measures="the peak speed of forward blood flow through the pulmonary valve",
    ),
    "left ventricular outflow tract gradient": KnowledgeBaseEntry(
        concept="Left Ventricular Outflow Tract Gradient",
        definition=(
            "The left ventricular outflow tract (LVOT) gradient is a Doppler measurement evaluating the pressure "
            "difference between the left ventricular chamber and the aorta as blood exits the heart."
        ),
        category="DOPPLER_MEASUREMENT",
        anatomy="Left Ventricular Outflow Tract",
        absent_description="Left ventricular outflow tract gradient: no gradient was reported across the LVOT.",
        what_it_measures="the pressure difference across the left ventricular outflow tract",
    ),
    "normal pulmonary valve ef slope": KnowledgeBaseEntry(
        concept="Normal Pulmonary Valve EF Slope",
        definition=(
            "The pulmonary valve E-F slope is an M-mode ultrasound measurement describing the rate of backward "
            "motion of the pulmonary valve leaflet during early diastole. A normal slope indicates unobstructed diastolic motion."
        ),
        category="VALVULAR_FINDING",
        anatomy="Pulmonary Valve",
        normal_description="The pulmonary valve E-F slope is described as normal.",
    ),
    "pulmonary valve ef slope": KnowledgeBaseEntry(
        concept="Pulmonary Valve EF Slope",
        definition=(
            "The pulmonary valve E-F slope is an ultrasound measurement of the diastolic motion of the "
            "pulmonary valve leaflet on M-mode echocardiography."
        ),
        category="VALVULAR_FINDING",
        anatomy="Pulmonary Valve",
        normal_description="The pulmonary valve E-F slope is described as normal.",
    ),
    "normal pulmonary valve a wave": KnowledgeBaseEntry(
        concept="Normal Pulmonary Valve A Wave",
        definition=(
            "The pulmonary valve A wave is an M-mode ultrasound contour deflection produced by the posterior "
            "movement of the pulmonary valve leaflet during right atrial contraction in late diastole."
        ),
        category="VALVULAR_FINDING",
        anatomy="Pulmonary Valve",
        normal_description="The pulmonary valve A wave is described as normal.",
    ),
    "pulmonary valve a wave": KnowledgeBaseEntry(
        concept="Pulmonary Valve A Wave",
        definition=(
            "The pulmonary valve A wave represents the movement of the pulmonary valve leaflet caused by "
            "atrial contraction in late diastole on M-mode imaging."
        ),
        category="VALVULAR_FINDING",
        anatomy="Pulmonary Valve",
        normal_description="The pulmonary valve A wave is described as normal.",
    ),
    "midsystolic notch": KnowledgeBaseEntry(
        concept="Midsystolic Notch",
        definition=(
            "A midsystolic notch is a waveform feature on pulmonary valve M-mode or Doppler tracings characterized by "
            "a transient partial closure or deceleration during mid-systole."
        ),
        category="VALVULAR_FINDING",
        anatomy="Pulmonary Valve",
        absent_description="Midsystolic notch: none was reported.",
        present_description="A midsystolic notch was identified on imaging.",
    ),

    # -----------------------------------------------------------------------
    # 8. OTHER FINDINGS (EFFUSION, THROMBUS, VEGETATION)
    # -----------------------------------------------------------------------
    "thrombus": KnowledgeBaseEntry(
        concept="Thrombus",
        definition=(
            "A thrombus is a stationary blood clot that can form on the inner walls or within the chambers "
            "of the heart (such as the left atrium or left ventricle)."
        ),
        category="THROMBUS",
        anatomy="Left Atrium, Left Ventricle",
        absent_description="Cardiac thrombus (clot): none was reported in the left atrium or left ventricle.",
        present_description="A thrombus was identified in the cardiac chambers.",
    ),
    "pericardial effusion": KnowledgeBaseEntry(
        concept="Pericardial Effusion",
        definition=(
            "A pericardial effusion refers to an abnormal collection of fluid within the pericardium, "
            "the protective double-layered sac that surrounds the heart."
        ),
        category="EFFUSION",
        anatomy="Pericardium",
        absent_description="Pericardial effusion: none was reported.",
        present_description="Pericardial effusion is noted in the report.",
    ),
    "vegetation": KnowledgeBaseEntry(
        concept="Vegetation",
        definition=(
            "A vegetation is an abnormal mass composed of fibrin, platelets, and cellular material "
            "that can form on a heart valve or endocardial surface."
        ),
        category="STRUCTURAL_FINDING",
        anatomy="Heart Valve",
        absent_description="Cardiac mass or vegetation: no evidence was reported.",
        present_description="A vegetation was noted on cardiac structures.",
    ),

    # -----------------------------------------------------------------------
    # 9. MEASUREMENTS (DIMENSIONS AND THICKNESSES)
    # -----------------------------------------------------------------------
    "aortic root diameter": KnowledgeBaseEntry(
        concept="Aortic Root Diameter",
        definition=(
            "Aortic root diameter measures the width of the initial segment of the aorta directly where "
            "it originates from the left ventricle."
        ),
        category="MEASUREMENT",
        anatomy="Aortic Root",
        what_it_measures="the diameter of the aortic root",
    ),
    "left atrial diameter": KnowledgeBaseEntry(
        concept="Left Atrial Diameter",
        definition=(
            "Left atrial diameter measures the internal dimension of the left atrium, the upper chamber "
            "that receives oxygenated blood from the lungs."
        ),
        category="MEASUREMENT",
        anatomy="Left Atrium",
        what_it_measures="the internal dimension of the left atrium",
    ),
    "left ventricular end-diastolic dimension": KnowledgeBaseEntry(
        concept="Left Ventricular End-Diastolic Dimension",
        definition=(
            "Left ventricular end-diastolic dimension (LVEDD) measures the internal width of the left ventricle "
            "when it is fully relaxed and filled with blood at the end of diastole."
        ),
        category="MEASUREMENT",
        anatomy="Left Ventricle",
        what_it_measures="the internal diameter of the left ventricle at end-diastole",
    ),
    "left ventricular end-systolic dimension": KnowledgeBaseEntry(
        concept="Left Ventricular End-Systolic Dimension",
        definition=(
            "Left ventricular end-systolic dimension (LVESD) measures the internal width of the left ventricle "
            "at the completion of contraction (systole), when the chamber reaches its smallest diameter."
        ),
        category="MEASUREMENT",
        anatomy="Left Ventricle",
        what_it_measures="the internal diameter of the left ventricle at end-systole",
    ),
    "interventricular septum thickness in diastole": KnowledgeBaseEntry(
        concept="Interventricular Septum Thickness in Diastole",
        definition=(
            "Interventricular septum thickness in diastole measures the thickness of the muscular partition "
            "separating the left and right ventricles during the resting phase of the cardiac cycle."
        ),
        category="MEASUREMENT",
        anatomy="Interventricular Septum",
        what_it_measures="the thickness of the interventricular septum during diastole",
    ),
    "interventricular septal thickness": KnowledgeBaseEntry(
        concept="Interventricular Septal Thickness",
        definition=(
            "Interventricular septal thickness measures the width of the muscular wall separating the "
            "left and right lower chambers of the heart."
        ),
        category="MEASUREMENT",
        anatomy="Interventricular Septum",
        what_it_measures="the thickness of the interventricular septum",
    ),
    "left ventricular posterior wall thickness in diastole": KnowledgeBaseEntry(
        concept="Left Ventricular Posterior Wall Thickness in Diastole",
        definition=(
            "Left ventricular posterior wall thickness in diastole measures the thickness of the back wall "
            "of the left ventricle during the resting phase of the cardiac cycle."
        ),
        category="MEASUREMENT",
        anatomy="Left Ventricle",
        what_it_measures="the thickness of the posterior wall of the left ventricle during diastole",
    ),
    "left ventricular posterior wall thickness": KnowledgeBaseEntry(
        concept="Left Ventricular Posterior Wall Thickness",
        definition=(
            "Left ventricular posterior wall thickness measures the muscular thickness of the posterior "
            "wall of the left ventricle."
        ),
        category="MEASUREMENT",
        anatomy="Left Ventricle",
        what_it_measures="the thickness of the posterior wall of the left ventricle",
    ),
}


def lookup_concept(concept_name: str) -> Optional[KnowledgeBaseEntry]:
    """
    Look up a concept in the explanation knowledge base.

    Matching is case-insensitive, normalizing whitespace and punctuation.
    Returns the KnowledgeBaseEntry if found, else None.
    """
    if not concept_name:
        return None

    clean = " ".join(concept_name.strip().lower().split())
    if clean in ECHO_KNOWLEDGE_BASE:
        return ECHO_KNOWLEDGE_BASE[clean]

    # Try removing trailing punctuation or qualifiers
    clean_no_punct = clean.replace(":", "").replace("-", " ").replace("  ", " ")
    if clean_no_punct in ECHO_KNOWLEDGE_BASE:
        return ECHO_KNOWLEDGE_BASE[clean_no_punct]

    # Partial / substring match for compound phrases
    for k, entry in ECHO_KNOWLEDGE_BASE.items():
        if k == clean or k == clean_no_punct:
            return entry

    return None
