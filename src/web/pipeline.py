"""
End-to-End Processing Pipeline for ClinRESET Web API.
Connects all 7 project phases into a unified document simplifier:
1. Parse -> 2. Segment -> 3. Rule Extract -> 4. Grounded Model Extract ->
5. Terminology Normalization -> 6. Interpretation -> 7. Explanation
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from src.explanation.engine import ClinicalExplainer
from src.extraction.hybrid_extractor import HybridClinicalExtractor
from src.extraction.model.concept_extractor import ConceptExtractor
from src.interpretation.engine import ClinicalInterpreter
from src.parsing.parser import PDFParser
from src.segmentation.segmenter import ReportSegmenter
from src.terminology.normalizer import TerminologyNormalizer
from .state import CONFIG_STATE

logger = logging.getLogger(__name__)


def process_clinical_pdf(
    pdf_path: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    filename: str = "report.pdf",
    report_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes complete end-to-end report simplification pipeline.
    """
    temp_file = None
    try:
        if pdf_bytes is not None:
            fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(fd, "wb") as f:
                f.write(pdf_bytes)
            actual_path = temp_path
            temp_file = temp_path
        elif pdf_path is not None:
            actual_path = pdf_path
        else:
            raise ValueError("Either pdf_path or pdf_bytes must be provided.")

        # Infer report modality from filename if not provided
        if not report_type:
            fname_lower = filename.lower()
            for mod in ["echo", "ct scans", "mri", "ultrasound", "xray", "general"]:
                if mod in fname_lower:
                    report_type = mod
                    break

        # -------------------------------------------------------------------
        # Phase 1: Parse PDF
        # -------------------------------------------------------------------
        parser = PDFParser()
        doc = parser.parse(actual_path)

        # -------------------------------------------------------------------
        # Phase 2: Segment Clauses & Filter Metadata
        # -------------------------------------------------------------------
        clauses = ReportSegmenter.segment_document(doc)

        # -------------------------------------------------------------------
        # Phase 3 & 4: Hybrid Extraction (Rules + Grounded Model)
        # -------------------------------------------------------------------
        # Configure ConceptExtractor using active methodology from UI
        active_backend = CONFIG_STATE.active_backend
        backend_kwargs = CONFIG_STATE.get_backend_kwargs()
        concept_ext = ConceptExtractor(
            backend=active_backend,
            **backend_kwargs,
        )
        hybrid_extractor = HybridClinicalExtractor(concept_extractor=concept_ext)

        extracted_findings: List[Dict[str, Any]] = []
        for clause in clauses:
            clause_facts = hybrid_extractor.extract_from_clause(clause)
            for f in clause_facts:
                val = f.measurement.value if f.measurement else None
                unit = f.measurement.unit if f.measurement else None
                ref_range = (
                    f.measurement.reference_range.raw_text
                    if (f.measurement and f.measurement.reference_range)
                    else None
                )
                extracted_findings.append({
                    "concept": f.concept,
                    "assertion": f.assertion,
                    "value": val,
                    "unit": unit,
                    "reference_range": ref_range,
                    "method": "Hybrid Rule + Grounded Model",
                    "source_text": f.source_text or clause.text,
                    "page_number": f.page_number,
                    "section_title": f.section_name or clause.section_name,
                })

        # -------------------------------------------------------------------
        # Phase 5: Terminology Normalization & SNOMED CT Enrichment
        # -------------------------------------------------------------------
        normalizer = TerminologyNormalizer(online=CONFIG_STATE.online_terminology)
        normalized_findings: List[Dict[str, Any]] = []

        for item in extracted_findings:
            raw_c = item["concept"]
            norm_res = normalizer.normalize(raw_c)
            merged = dict(item)
            merged["preferred_term"] = norm_res.preferred_term
            merged["snomed_id"] = norm_res.snomed_id
            merged["radlex_id"] = norm_res.radlex_id
            merged["layman_synonym"] = norm_res.layman_synonym
            merged["organ_system"] = norm_res.organ_system
            merged["is_known"] = norm_res.is_known
            normalized_findings.append(merged)

        # Persist newly learned terminology to disk for instantaneous offline access
        normalizer.save_cache()

        # -------------------------------------------------------------------
        # Phase 6: Deterministic Interpretation & Triage Alerts
        # -------------------------------------------------------------------
        interpretation = ClinicalInterpreter.interpret_report(normalized_findings)

        # Attach interpretation results back to findings
        for finding, interp_res in zip(normalized_findings, interpretation.results):
            finding["comparison"] = interp_res.comparison.value
            finding["significance"] = interp_res.significance.value
            finding["alert_level"] = interp_res.alert_level.value
            finding["clinical_basis"] = interp_res.basis

        # -------------------------------------------------------------------
        # Phase 7: Grounded Patient Explanation
        # -------------------------------------------------------------------
        explanation = ClinicalExplainer.explain_report(
            findings=normalized_findings,
            report_type=report_type,
            use_llm=False,  # default to deterministic template for instant reliability
        )

        interp_dict = interpretation.to_dict()
        interp_dict["triage_summary"] = interpretation.alert_counts

        return {
            "filename": filename,
            "report_type": report_type or "General Clinical Report",
            "page_count": len(doc.pages),
            "section_count": len(doc.sections),
            "clause_count": len(clauses),
            "findings_count": len(normalized_findings),
            "active_methodology": active_backend,
            "patient_explanation": explanation.to_dict(),
            "interpretation": interp_dict,
            "findings": normalized_findings,
            "clusters": [
                {
                    "cluster_name": c.cluster_name,
                    "matched_concepts": c.matched_concepts,
                    "findings": c.matched_concepts,
                    "organ_system": c.organ_system,
                    "explanation": c.explanation,
                }
                for c in interpretation.clusters
            ],
            "sections": [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in doc.sections],
        }

    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
