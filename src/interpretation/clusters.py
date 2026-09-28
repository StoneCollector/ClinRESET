"""
Non-causal contextual clustering for clinical findings in ClinRESET.
Groups related concepts that co-occur in standard medical reports
without speculating on causation or pathology.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .models import FindingCluster

logger = logging.getLogger(__name__)

# Predefined domain clustering definitions
CLUSTER_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "Concentric LVH & Wall Structure Cluster",
        "organ_system": "Cardiovascular",
        "keywords": ["hypertrophy", "lvh", "septum", "ivsd", "diastolic", "posterior wall", "lvedd"],
        "explanation": (
            "These findings and measurements evaluate left ventricular wall thickness and diastolic relaxation; "
            "they commonly co-occur in echocardiographic evaluation of cardiac structure without establishing causation."
        ),
    },
    {
        "name": "Systolic Function & Ejection Fraction Cluster",
        "organ_system": "Cardiovascular",
        "keywords": ["ejection fraction", "fractional shortening", "systolic", "lvef", "wall motion", "rwma"],
        "explanation": (
            "These metrics and observations assess left ventricular pumping performance and chamber contractility "
            "reported in parallel."
        ),
    },
    {
        "name": "Pulmonary & Right Heart Hemodynamics Cluster",
        "organ_system": "Cardiovascular",
        "keywords": ["tricuspid", "pasp", "pulmonary artery", "right ventricle", "rv systolic"],
        "explanation": (
            "These parameters reflect right ventricular and pulmonary vascular pressures routinely assessed together "
            "during Doppler examination."
        ),
    },
    {
        "name": "Pleuropulmonary Findings Cluster",
        "organ_system": "Respiratory",
        "keywords": ["pleural effusion", "pneumothorax", "consolidation", "infiltrate", "opacity", "lung fields", "atelectasis"],
        "explanation": (
            "These chest imaging findings document the status of the lung parenchyma and pleural spaces, "
            "presented as co-occurring observations."
        ),
    },
    {
        "name": "Hepatobiliary Evaluation Cluster",
        "organ_system": "Gastrointestinal",
        "keywords": ["liver", "hepatomegaly", "gallbladder", "cholelithiasis", "calculus", "calculi", "parenchymal", "bile duct", "cbd"],
        "explanation": (
            "These ultrasound/CT findings evaluate liver size, parenchymal texture, and biliary gallbladder integrity."
        ),
    },
    {
        "name": "Spinal Alignment & Disc Space Cluster",
        "organ_system": "Musculoskeletal",
        "keywords": ["lordosis", "disc bulge", "spondylolisthesis", "subluxation", "dislocation", "facet", "ivd", "vertebra"],
        "explanation": (
            "These radiographic findings evaluate spinal column curvature, intervertebral disc spacing, and vertebral alignment."
        ),
    },
]


class ContextClusterer:
    """Discovers contextual groupings among extracted report findings."""

    @classmethod
    def find_clusters(cls, concepts: List[str]) -> List[FindingCluster]:
        """
        Identifies report-level clusters among present concepts.
        Requires at least 2 distinct concepts to trigger a cluster.
        """
        if not concepts or len(concepts) < 2:
            return []

        matched_clusters: List[FindingCluster] = []

        for defn in CLUSTER_DEFINITIONS:
            matched_in_report: List[str] = []
            keywords = defn["keywords"]

            for concept in concepts:
                c_lower = concept.lower()
                if any(kw in c_lower for kw in keywords):
                    if concept not in matched_in_report:
                        matched_in_report.append(concept)

            if len(matched_in_report) >= 2:
                matched_clusters.append(
                    FindingCluster(
                        cluster_name=defn["name"],
                        matched_concepts=matched_in_report,
                        organ_system=defn["organ_system"],
                        explanation=defn["explanation"],
                    )
                )

        return matched_clusters
