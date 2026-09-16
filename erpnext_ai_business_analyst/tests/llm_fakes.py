"""
Test doubles for LLMClient and EmbeddingClient — deterministic fakes so
planner/retrieval tests exercise the real decision/validation and
similarity-ranking paths without making real API calls.
"""

from __future__ import annotations

from erpnext_ai_business_analyst.agent.llm.base import LLMClient
from erpnext_ai_business_analyst.agent.llm.embedding_client import EmbeddingClient


class ScriptedLLMClient(LLMClient):
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
        self.calls.append((system_prompt, user_prompt))
        if not self._responses:
            raise AssertionError(
                "ScriptedLLMClient ran out of scripted responses — the planner "
                "asked for more decisions than the test scripted."
            )
        return self._responses.pop(0)


class FakeEmbeddingClient(EmbeddingClient):
    """Returns a pre-assigned vector for each exact text it's asked to embed
    — no real embedding model involved. `vectors_by_text` maps the exact
    string passed to `embed()` to the vector to return; `embed()` raises if
    asked for text it wasn't given a vector for, surfacing test setup bugs
    rather than silently returning something meaningless."""

    def __init__(self, vectors_by_text: dict[str, list[float]]):
        self._vectors_by_text = dict(vectors_by_text)
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        if text not in self._vectors_by_text:
            raise AssertionError(f"FakeEmbeddingClient has no vector configured for: {text!r}")
        return self._vectors_by_text[text]