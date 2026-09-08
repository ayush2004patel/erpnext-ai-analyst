"""
Test double for LLMClient — returns pre-scripted responses in order, so
planner tests exercise the real decision/validation path without making
real API calls.
"""

from __future__ import annotations

from erpnext_ai_business_analyst.agent.llm.base import LLMClient


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