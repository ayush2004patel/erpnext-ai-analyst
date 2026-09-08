"""
Provider-agnostic LLM interface. The planner depends only on this
interface, never on a specific provider's SDK — Anthropic is the first
implementation; OpenAI/local models can be added later without touching
planner.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
        """Return the raw text completion. Callers are responsible for
        parsing/validating structured content out of the returned string —
        this interface makes no assumptions about response format."""
        raise NotImplementedError