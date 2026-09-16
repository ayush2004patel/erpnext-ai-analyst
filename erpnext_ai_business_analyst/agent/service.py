"""
The composed entry point: run an investigation, then persist it. This is
what Step 12's chat UI (via a whitelisted API method) will actually call —
callers shouldn't need to know that running and persisting are two
separate steps under the hood.
"""

from __future__ import annotations

from erpnext_ai_business_analyst.agent.llm.base import LLMClient
from erpnext_ai_business_analyst.agent.llm.embedding_client import EmbeddingClient
from erpnext_ai_business_analyst.agent.persistence import save_investigation_log
from erpnext_ai_business_analyst.agent.planner import (
    DEFAULT_MAX_HOPS,
    DEFAULT_TOP_K,
    InvestigationResult,
    run_investigation,
)
from erpnext_ai_business_analyst.skills.registry import SkillRegistry
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


def investigate(
    question: str,
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
    llm_client: LLMClient,
    initial_inputs: dict | None = None,
    max_hops: int = DEFAULT_MAX_HOPS,
    embedding_client: EmbeddingClient | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[InvestigationResult, str]:
    """Runs the investigation, persists it, and returns both the result and
    the new AI Investigation Log doc's name."""
    result = run_investigation(
        question=question,
        tool_registry=tool_registry,
        skill_registry=skill_registry,
        llm_client=llm_client,
        initial_inputs=initial_inputs,
        max_hops=max_hops,
        embedding_client=embedding_client,
        top_k=top_k,
    )
    log_name = save_investigation_log(question, result)
    return result, log_name