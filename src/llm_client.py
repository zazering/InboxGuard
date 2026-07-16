"""Thin wrapper around the Ollama /api/chat endpoint."""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config):
        self.base_url = config.get("llm.ollama_url", "http://localhost:11434").rstrip("/")
        self.model    = config.get("llm.model", "qwen2.5:3b")
        self.timeout  = config.get("llm.timeout", 45)

    # ── Health check ───────────────────────────────────────────────────────

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def model_is_pulled(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            names = [m["name"] for m in r.json().get("models", [])]
            return any(self.model in n for n in names)
        except Exception:
            return False

    # ── Inference ──────────────────────────────────────────────────────────

    def generate(self, prompt: str, system: str = None) -> Optional[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model":    self.model,
            "messages": messages,
            "stream":   False,
            "options": {
                "temperature": 0.1,   # Low for deterministic triage
                "num_predict": 256,   # Short answer enough for JSON
                "num_ctx":     4096,
            },
        }

        try:
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()["message"]["content"].strip()

        except requests.exceptions.ConnectionError:
            logger.error(
                "Cannot reach Ollama. "
                "Make sure it is running: systemctl --user start ollama"
            )
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Ollama timed out after {self.timeout}s for model '{self.model}'")
            return None
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return None
