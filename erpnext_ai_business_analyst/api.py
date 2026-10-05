"""
Whitelisted API for the chat UI. This is the composition root — the one
place allowed to instantiate a concrete LLMClient (OllamaClient) directly.
Everything downstream (service.investigate, planner, skills, tools) stays
provider-agnostic.

Path note: this file sits at the top level of the inner app package
(erpnext_ai_business_analyst/api.py), same depth as tools/, skills/,
agent/ — NOT under the module-folder-nested doctype/page path. Only
DocTypes and Pages (things with a "module" field) need the triple-nested
`erpnext_ai_business_analyst/erpnext_ai_business_analyst/erpnext_ai_business_analyst/`
path learned the hard way in Step 10.
"""

from __future__ import annotations

import frappe

from erpnext_ai_business_analyst.agent.llm.ollama_client import OllamaClient
from erpnext_ai_business_analyst.agent.llm.ollama_embedding_client import OllamaEmbeddingClient
from erpnext_ai_business_analyst.agent.service import investigate
from erpnext_ai_business_analyst.skills.registry import SkillRegistry
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


@frappe.whitelist()
def ask_question(question: str) -> dict:
    if not question or not question.strip():
        frappe.throw("Question is required")

    llm_client = OllamaClient()  # reads ollama_model/ollama_host from site_config
    embedding_client = OllamaEmbeddingClient()  # reads ollama_embedding_model/ollama_host

    result, log_name = investigate(
        question=question,
        tool_registry=ToolRegistry.get(),
        skill_registry=SkillRegistry.get(),
        llm_client=llm_client,
        embedding_client=embedding_client,
    )

    return {
        "status": result.status,
        "hop_count": result.hop_count,
        "category": result.category,
        "findings": [
            {"claim": f.claim, "confidence": f.confidence}
            for f in result.findings
        ],
        "steps": [
            {"skill_name": s.skill_name, "status": s.result.status}
            for s in result.history
        ],
        "evidence": [
            {
                "id": e.id,
                "source_tool": e.source_tool,
                "summary": e.summary,
                "records": e.records,
            }
            for e in result.evidence
        ],
        "decision_errors": result.decision_errors,
        "log_name": log_name,
    }


@frappe.whitelist()
def get_inventory_health_summary() -> dict:
    """Return the highest-priority inventory exceptions without using the LLM."""
    tool_registry = ToolRegistry.get()
    skill_registry = SkillRegistry.get()
    cards = [
        ("inventory.stockout_risk", "Stockout risk", "danger"),
        ("inventory.dead_stock", "Dead stock", "warning"),
        ("inventory.overstock", "Overstock", "warning"),
        ("inventory.expiring_batches", "Expiring batches", "danger"),
        ("inventory.negative_stock", "Negative stock", "danger"),
    ]
    summary = []
    for skill_name, label, tone in cards:
        result = skill_registry.get_skill(skill_name).run(tool_registry)
        summary.append({
            "skill_name": skill_name,
            "label": label,
            "tone": tone,
            "status": result.status.value,
            "count": len(result.findings),
            "examples": [finding.claim for finding in result.findings[:3]],
            "error": result.error,
        })
    return {"cards": summary}
