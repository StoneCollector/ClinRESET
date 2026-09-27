"""
Classification layer for the ClinRESET NLP pipeline.

This package implements Phase 2: rule-based, weighted-signature report
type identification.

Design principles
-----------------
- Operates exclusively on the ExtractionResult produced by Phase 1.
- No PDF re-processing.
- No ML/transformer/embedding models.
- Fully explainable: every classification carries traceable evidence.
- Configurable: report signatures live in a separate module and can be
  extended without touching classifier logic.

Out of scope (deferred to later phases):
    clinical NER, abnormality detection, patient-facing simplification,
    diagnosis, medical inference.
"""

from classification.classifier import classify
from classification.models import ClassificationResult

__all__ = ["classify", "ClassificationResult"]
