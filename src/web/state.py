"""
Runtime configuration state for ClinRESET Web App.
Maintains active concept extraction methodology and dynamic credentials.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def _load_dotenv_if_exists() -> None:
    for candidate in [".env", os.path.join(os.path.dirname(__file__), "../../../.env")]:
        abs_path = os.path.abspath(candidate)
        if os.path.isfile(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
                break
            except Exception:
                pass


_load_dotenv_if_exists()


class AppConfigState:
    """Singleton state holding user-configured methodologies and credentials."""

    def __init__(self):
        self.active_backend: str = os.environ.get("LLM_BACKEND", "heuristic")
        self.ollama_url: str = "http://localhost:11434"
        self.ollama_model: str = "qwen2.5:1.5b"
        self.hf_token: Optional[str] = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
        self.hf_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
        self.transformers_model: str = "Qwen/Qwen2.5-1.5B-Instruct"
        self.online_terminology: bool = False

    def get_backend_kwargs(self) -> Dict[str, Any]:
        """Returns kwargs matching the active backend configuration."""
        b = self.active_backend.lower()
        if b == "ollama":
            return {"base_url": self.ollama_url, "model_name": self.ollama_model}
        elif b == "hf_api":
            return {"api_token": self.hf_token, "model_name": self.hf_model}
        elif b == "transformers":
            return {"model_name": self.transformers_model}
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_backend": self.active_backend,
            "online_terminology": self.online_terminology,
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "hf_token_set": bool(self.hf_token),
            "hf_model": self.hf_model,
            "transformers_model": self.transformers_model,
            "ollama": {
                "base_url": self.ollama_url,
                "model_name": self.ollama_model,
            },
            "hf_api": {
                "has_token": bool(self.hf_token),
                "model_id": self.hf_model,
            },
            "transformers": {
                "model_name": self.transformers_model,
            },
        }


# Global in-memory configuration instance
CONFIG_STATE = AppConfigState()
