"""
Model Plugins and Methodology Selector for ClinRESET Concept Extraction.
Allows seamless switching between:
1. 'heuristic'   : Pure deterministic grounded NLP (offline, instant, 0 dependencies)
2. 'ollama'      : Local Ollama / LM Studio server (fast 4-bit GGUF, ideal for Windows)
3. 'hf_api'      : Hugging Face Serverless Inference API (0 local weights)
4. 'transformers': Local PyTorch / Transformers model (direct weights from HF)
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.extraction.rules.assertions import AssertionClassifier
from .grounding import GroundingValidator
from .prompt import build_prompt

logger = logging.getLogger(__name__)


class BaseModelPlugin(ABC):
    """Abstract base class for concept extraction backends."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if required dependencies, servers, or credentials are present."""
        pass

    @abstractmethod
    def extract(self, sentence: str) -> List[Dict[str, Any]]:
        """Extracts candidate items: [{'concept': '...', 'assertion': 'PRESENT|ABSENT|NORMAL'}]."""
        pass


class HeuristicPlugin(BaseModelPlugin):
    """
    Pure deterministic grounded NLP engine.
    Runs on standard library + regex. Instantaneous, offline, 0 memory overhead.
    """
    name = "heuristic"

    def __init__(self, **kwargs):
        pass

    def is_available(self) -> bool:
        return True

    def extract(self, sentence: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        sub_clauses = re.split(
            r"(?:[;\n]+|,\s*(?=(?:no|not|normal|with|negative|without|mild|moderate|severe)\b)|\s+with\s+(?=(?:mild|moderate|severe|patchy|diffuse|no|increased|decreased)\b)|\band\s+(?=(?:no|small|large|diffuse)\b))",
            sentence,
            flags=re.IGNORECASE
        )

        for clause in sub_clauses:
            clause = clause.strip(" \t,;.")
            if not clause:
                continue

            assertion = AssertionClassifier.classify(clause)

            # Check for coordinated terms separated by slash e.g. "calculus / mass"
            if " / " in clause or "/" in clause:
                slash_parts = [p.strip() for p in re.split(r"\s*/\s*", clause) if p.strip()]
                if len(slash_parts) > 1 and all(len(p.split()) <= 3 for p in slash_parts):
                    for part in slash_parts:
                        c_clean = self._clean_finding_term(part)
                        if c_clean:
                            items.append({"concept": c_clean, "assertion": assertion})
                    continue

            concept = self._clean_finding_term(clause)
            if concept:
                items.append({"concept": concept, "assertion": assertion})

        return items

    @classmethod
    def _clean_finding_term(cls, text: str) -> Optional[str]:
        # Strip measurements
        clean = re.sub(r"\([~-]?\s*\d+(?:\.\d+)?\s*(?:cm|mm|%|m/s|mmHg|cc)\)", "", text, flags=re.IGNORECASE)
        clean = re.sub(r"\bmeasuring\s*~?\s*\d+(?:\.\d+)?\s*(?:cm|mm|%|m/s|mmHg|cc)\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"[~-]?\s*\d+(?:\.\d+)?\s*(?:cm|mm|%|m/s|mmHg|cc)\b", "", clean, flags=re.IGNORECASE)

        # Strip assertion prefixes
        clean = re.sub(
            r"^(?:no\s+evidence\s+of(?:\s+any)?|no\s+e/o(?:\s+any)?|no\s+sign\s+of|negative\s+for|without|no|not|mild|moderate|large|small|two\s+small|echogenic|focal|patchy|diffuse)\s+",
            "", clean, flags=re.IGNORECASE
        )

        # Strip observation verbs
        clean = re.sub(
            r"\s+(?:is\s+seen|are\s+seen|seen|noted|detected|identified|present|normal|intact|clear|unremarkable|appears?\s+normal|within\s+normal\s+limits|wnl|opening\s+well|opens\s+well)\.?$",
            "", clean, flags=re.IGNORECASE
        )

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

        if not clean or len(clean) < 2 or clean.lower() in {"is", "are", "shows", "in its lumen", "seen in its lumen"}:
            return None

        clean = re.sub(r"\s+in\s+its\s+lumen$", "", clean, flags=re.IGNORECASE)
        return clean


class OllamaPlugin(BaseModelPlugin):
    """
    Connects to local Ollama (e.g. `ollama run qwen2.5:1.5b`) or LM Studio.
    Uses standard HTTP calls via standard library (urllib).
    """
    name = "ollama"

    def __init__(self, model_name: str = "qwen2.5:1.5b", base_url: str = "http://localhost:11434", **kwargs):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def extract(self, sentence: str) -> List[Dict[str, Any]]:
        prompt_text = build_prompt(sentence)
        payload = {
            "model": self.model_name,
            "prompt": prompt_text,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 128
            }
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                response_text = result.get("response", "")
                return self._parse_json(response_text)
        except Exception as e:
            logger.warning(f"Ollama request failed: {e}. Falling back to heuristic.")
            return HeuristicPlugin().extract(sentence)

    @staticmethod
    def _parse_json(raw: str) -> List[Dict[str, Any]]:
        i = raw.find("{")
        if i >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(raw[i:])
                items = obj.get("items")
                if isinstance(items, list):
                    return [x for x in items if isinstance(x, dict)]
            except Exception:
                pass
        return []


class HuggingFaceApiPlugin(BaseModelPlugin):
    """
    Hugging Face Serverless Inference API.
    Zero local download required; uses free HF access token.
    """
    name = "hf_api"

    def __init__(
        self,
        model_id: str = "Qwen/Qwen2.5-1.5B-Instruct",
        api_token: Optional[str] = None,
        model_name: Optional[str] = None,
        **kwargs
    ):
        raw_id = model_name or model_id or "Qwen/Qwen2.5-1.5B-Instruct"
        # Sanitize model_id in case user entered URL or leading/trailing slashes
        clean_id = (
            raw_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .strip("/")
            .strip()
        )
        self.model_id = clean_id
        self.api_token = api_token or os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
        self.endpoint = f"https://router.huggingface.co/hf-inference/models/{self.model_id}"

    def is_available(self) -> bool:
        return bool(self.api_token)

    def extract(self, sentence: str) -> List[Dict[str, Any]]:
        if not self.api_token:
            logger.warning("No Hugging Face API token set. Falling back to heuristic.")
            return HeuristicPlugin().extract(sentence)

        prompt_text = build_prompt(sentence)
        payload = {
            "inputs": prompt_text,
            "parameters": {
                "max_new_tokens": 128,
                "return_full_text": False,
                "temperature": 0.01
            }
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_token.strip()}"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                gen_text = ""
                if isinstance(result, list) and result:
                    gen_text = result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    gen_text = result.get("generated_text", "")

                if gen_text:
                    return OllamaPlugin._parse_json(gen_text)
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            logger.warning(f"HF API HTTP {e.code} error: {err_body or e.reason}. Falling back to heuristic.")
        except Exception as e:
            logger.warning(f"HF API inference failed: {e}. Falling back to heuristic.")

        return HeuristicPlugin().extract(sentence)


class TransformersPlugin(BaseModelPlugin):
    """
    Direct PyTorch / Transformers backend running model weights locally.
    """
    name = "transformers"

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct", **kwargs):
        self.model_name = model_name
        self._model = None
        self._tokenizer = None

    def is_available(self) -> bool:
        try:
            import torch
            import transformers
            return True
        except ImportError:
            return False

    def load_model(self):
        if self._model is not None:
            return
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        logger.info(f"Loading local weights for {self.model_name}...")
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map="auto" if torch.cuda.is_available() else "cpu",
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
        )

    def extract(self, sentence: str) -> List[Dict[str, Any]]:
        if not self.is_available():
            logger.warning("Torch/Transformers not installed. Run 'pip install torch transformers'. Falling back to heuristic.")
            return HeuristicPlugin().extract(sentence)

        try:
            self.load_model()
            import torch
            prompt_text = build_prompt(sentence)
            ids = self._tokenizer(prompt_text, return_tensors="pt").to(self._model.device)
            with torch.no_grad():
                out = self._model.generate(
                    **ids,
                    max_new_tokens=128,
                    do_sample=False,
                    pad_token_id=self._tokenizer.eos_token_id
                )
            generated = self._tokenizer.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
            return OllamaPlugin._parse_json(generated)
        except Exception as e:
            logger.warning(f"Transformers generation failed: {e}. Falling back to heuristic.")
            return HeuristicPlugin().extract(sentence)


class ModelSelector:
    """
    Methodology selector allowing dynamic switching between concept extraction backends.
    """

    AVAILABLE_PLUGINS: Dict[str, Any] = {
        "heuristic": HeuristicPlugin,
        "ollama": OllamaPlugin,
        "hf_api": HuggingFaceApiPlugin,
        "transformers": TransformersPlugin,
    }

    @classmethod
    def list_available_backends(cls) -> Dict[str, bool]:
        """Returns dict of backend names and their current operational availability."""
        status = {}
        for name, plugin_cls in cls.AVAILABLE_PLUGINS.items():
            try:
                inst = plugin_cls()
                status[name] = inst.is_available()
            except Exception:
                status[name] = False
        return status

    @classmethod
    def get_backend(cls, backend_name: Optional[str] = None, **kwargs) -> BaseModelPlugin:
        """
        Instantiates requested backend.
        Priority:
        1. Explicit backend_name argument ('heuristic', 'ollama', 'hf_api', 'transformers')
        2. Environment variable 'LLM_BACKEND'
        3. Automatic fallback: Ollama (if running) -> HF API (if token set) -> Transformers (if torch installed) -> Heuristic (default)
        """
        chosen = backend_name or os.environ.get("LLM_BACKEND")

        if chosen:
            chosen = chosen.lower().strip()
            if chosen in cls.AVAILABLE_PLUGINS:
                return cls.AVAILABLE_PLUGINS[chosen](**kwargs)
            else:
                logger.warning(f"Unknown backend '{chosen}'. Valid choices: {list(cls.AVAILABLE_PLUGINS.keys())}")

        # Automatic detection
        ollama = OllamaPlugin(**kwargs)
        if ollama.is_available():
            logger.info("Auto-detected local Ollama server running. Using 'ollama' backend.")
            return ollama

        hf_api = HuggingFaceApiPlugin(**kwargs)
        if hf_api.is_available():
            logger.info("Auto-detected Hugging Face API key. Using 'hf_api' backend.")
            return hf_api

        trans = TransformersPlugin(**kwargs)
        if trans.is_available():
            logger.info("Auto-detected PyTorch & Transformers installed. Using 'transformers' backend.")
            return trans

        logger.info("Using default high-precision 'heuristic' concept extraction backend.")
        return HeuristicPlugin()
