"""
Ollama implementation of LLMClient — the default/first provider for V1.

Runs against a local (or remote) Ollama server over its HTTP API. No API
key, no external dependency beyond `requests` (already present in any
Frappe environment). Model and host are configurable via site_config.json,
both with sensible defaults if unset:

    bench --site business-analyst set-config ollama_model "qwen2.5:3b-instruct"
    bench --site business-analyst set-config ollama_host "http://localhost:11434"

Adding a second provider (Groq, Anthropic, etc.) later means writing
another LLMClient implementation next to this one — planner.py and
agent/decision.py never need to change, since they only depend on the
LLMClient interface.
"""

from __future__ import annotations

import frappe
import requests

from erpnext_ai_business_analyst.agent.llm.base import LLMClient

DEFAULT_MODEL = "qwen2.5:3b-instruct"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 180


class OllamaClient(LLMClient):
    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or frappe.conf.get("ollama_model") or DEFAULT_MODEL
        self.host = (host or frappe.conf.get("ollama_host") or DEFAULT_HOST).rstrip("/")

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
        response = requests.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                # temperature=0: the planner's decisions should be as
                # reproducible as possible, same spirit as the deterministic
                # confidence bands used throughout the Skills.
                "options": {"temperature": 0, "num_predict": max_tokens},
            },
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"Unexpected Ollama response shape: {data}") from e