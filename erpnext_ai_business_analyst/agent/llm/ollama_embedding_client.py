"""
Ollama implementation of EmbeddingClient — used for semantic Skill
retrieval at the planner's hop-0 candidate selection (see
agent/retrieval.py). Not involved in the RUN/CONCLUDE decision itself —
that's still OllamaClient/decision.py, untouched.

Model and host are configurable via site_config.json, both with sensible
defaults if unset:

    bench --site business-analyst set-config ollama_embedding_model "nomic-embed-text"
    bench --site business-analyst set-config ollama_host "http://localhost:11434"

(ollama_host is shared with OllamaClient — same server, different endpoint.)
"""

from __future__ import annotations

import frappe
import requests

from erpnext_ai_business_analyst.agent.llm.embedding_client import EmbeddingClient

DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 60


class OllamaEmbeddingClient(EmbeddingClient):
    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or frappe.conf.get("ollama_embedding_model") or DEFAULT_EMBEDDING_MODEL
        self.host = (host or frappe.conf.get("ollama_host") or DEFAULT_HOST).rstrip("/")

    def embed(self, text: str) -> list[float]:
        response = requests.post(
            f"{self.host}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        try:
            return data["embedding"]
        except KeyError as e:
            raise RuntimeError(f"Unexpected Ollama embeddings response shape: {data}") from e