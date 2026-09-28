"""
Concept Extractor for clinical clauses.
Integrates small language models (Qwen2.5-1.5B) and grounded NLP concept extraction.
Always enforces GroundingValidator to eliminate hallucinations.
"""

import json
import re
import logging
from typing import List, Dict, Any, Optional

from src.extraction.rules.assertions import AssertionClassifier
from .grounding import GroundingValidator
from .prompt import build_prompt

logger = logging.getLogger(__name__)


class ConceptExtractor:
    """Extracts grounded finding concepts and assertions from clinical sentences."""

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct", use_local_weights: bool = False):
        self.model_name = model_name
        self.use_local_weights = use_local_weights
        self._model = None
        self._tokenizer = None

        if self.use_local_weights:
            self._init_local_model()

    def _init_local_model(self):
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
            logger.info(f"Loading local model: {self.model_name}")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto" if torch.cuda.is_available() else "cpu",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
        except Exception as e:
            logger.warning(f"Could not load local weights for {self.model_name}: {e}. Falling back to grounded extractor.")
            self._model = None
            self._tokenizer = None

    def extract_concepts(self, sentence: str) -> List[Dict[str, Any]]:
        """
        Extracts list of {"concept": "...", "assertion": "PRESENT|ABSENT|NORMAL"} from sentence.
        Applies GroundingValidator to guarantee zero hallucinations.
        """
        if not sentence or not sentence.strip():
            return []

        # 1. Try local transformers model if loaded
        if self._model is not None and self._tokenizer is not None:
            raw_output = self._call_transformers(sentence)
            items = self._parse_json_response(raw_output)
            if items is not None:
                return GroundingValidator.filter_items(items, sentence)

        # 2. High-precision Grounded NLP extraction (Fast & Offline)
        items = self._extract_grounded_heuristic(sentence)
        return GroundingValidator.filter_items(items, sentence)

    def _call_transformers(self, sentence: str) -> str:
        import torch
        prompt_text = build_prompt(sentence)
        try:
            text = self._tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt_text}],
                tokenize=False,
                add_generation_prompt=True
            )
        except Exception:
            text = prompt_text

        ids = self._tokenizer(text, return_tensors="pt", add_special_tokens=False).to(self._model.device)
        with torch.no_grad():
            out = self._model.generate(
                **ids,
                max_new_tokens=120,
                do_sample=False,
                repetition_penalty=1.05,
                pad_token_id=self._tokenizer.eos_token_id
            )
        return self._tokenizer.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)

    @staticmethod
    def _parse_json_response(raw: str) -> Optional[List[Dict[str, Any]]]:
        if not raw:
            return None
        i = raw.find("{")
        if i < 0:
            return None
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[i:])
            items = obj.get("items") if isinstance(obj, dict) else None
            if isinstance(items, list) and all(isinstance(x, dict) for x in items):
                return items
        except Exception:
            pass
        return None

    @classmethod
    def _extract_grounded_heuristic(cls, sentence: str) -> List[Dict[str, Any]]:
        """
        High-precision grounded parser for clinical sentences.
        Splits coordinate concepts (e.g. 'subluxation / dislocation / spondylolisthesis')
        and assigns assertion status based on assertion cues.
        """
        items: List[Dict[str, Any]] = []

        # Split clauses by comma or coordinating words
        sub_clauses = re.split(r"(?:,\s*(?=(?:no|not|normal|with)\b)|\s+with\s+(?=(?:mild|moderate|severe|patchy|diffuse|no)\b)|\band\s+(?=(?:no|small|large|diffuse)\b))", sentence, flags=re.IGNORECASE)

        for clause in sub_clauses:
            clause = clause.strip(" \t,;.")
            if not clause:
                continue

            assertion = AssertionClassifier.classify(clause)

            # Check for multiple coordinated terms separated by slash e.g. "calculus / mass" or "subluxation / dislocation / spondylolisthesis"
            if " / " in clause or "/" in clause:
                slash_parts = [p.strip() for p in re.split(r"\s*/\s*", clause) if p.strip()]
                # If these are coordinated finding terms
                if len(slash_parts) > 1 and all(len(p.split()) <= 3 for p in slash_parts):
                    for part in slash_parts:
                        c_clean = cls._clean_finding_term(part)
                        if c_clean:
                            items.append({"concept": c_clean, "assertion": assertion})
                    continue

            # Single or primary concept extraction
            concept = cls._clean_finding_term(clause)
            if concept:
                items.append({"concept": concept, "assertion": assertion})

        return items

    @classmethod
    def _clean_finding_term(cls, text: str) -> Optional[str]:
        """Cleans and isolates finding concept name, stripping measurements and assertion prefixes."""
        # 1. Strip measurements like (~15.8cm), measuring ~4mm, ~32.6mm
        clean = re.sub(r"\([~-]?\s*\d+(?:\.\d+)?\s*(?:cm|mm|%|m/s|mmHg|cc)\)", "", text, flags=re.IGNORECASE)
        clean = re.sub(r"\bmeasuring\s*~?\s*\d+(?:\.\d+)?\s*(?:cm|mm|%|m/s|mmHg|cc)\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"[~-]?\s*\d+(?:\.\d+)?\s*(?:cm|mm|%|m/s|mmHg|cc)\b", "", clean, flags=re.IGNORECASE)

        # 2. Strip assertion prefixes
        clean = re.sub(
            r"^(?:no\s+evidence\s+of(?:\s+any)?|no\s+e/o(?:\s+any)?|no\s+sign\s+of|negative\s+for|without|no|not|mild|moderate|large|small|two\s+small|echogenic|focal|patchy|diffuse)\s+",
            "", clean, flags=re.IGNORECASE
        )

        # 3. Strip trailing observation verbs
        clean = re.sub(
            r"\s+(?:is\s+seen|are\s+seen|seen|noted|detected|identified|present|normal|intact|clear|unremarkable|appears?\s+normal|within\s+normal\s+limits|wnl|opening\s+well|opens\s+well)\.?$",
            "", clean, flags=re.IGNORECASE
        )

        # 4. Remove colon structure (e.g. "Liver: is enlarged" -> "liver")
        if ":" in clean:
            parts = clean.split(":", 1)
            prefix = parts[0].strip()
            suffix = parts[1].strip()
            if not suffix or "normal" in suffix.lower() or "enlarged" in suffix.lower():
                clean = prefix
            else:
                clean = f"{prefix} {suffix}"

        clean = re.sub(r"^[ \t:.-]+|[ \t:.-]+$", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()

        # Reject pure non-concept strings
        if not clean or len(clean) < 2 or clean.lower() in {"is", "are", "shows", "in its lumen", "seen in its lumen"}:
            return None

        # Clean trailing locations like 'seen in lower calyx' -> 'calculi in lower calyx'
        clean = re.sub(r"\s+in\s+its\s+lumen$", "", clean, flags=re.IGNORECASE)
        return clean
