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
from frappe.utils import cint

from erpnext_ai_business_analyst.agent.llm.ollama_client import OllamaClient
from erpnext_ai_business_analyst.agent.llm.ollama_embedding_client import OllamaEmbeddingClient
from erpnext_ai_business_analyst.agent.classifier import classify_question
from erpnext_ai_business_analyst.agent.persistence import save_investigation_log
from erpnext_ai_business_analyst.agent.planner import InvestigationResult, InvestigationStep, run_investigation
from erpnext_ai_business_analyst.reports.catalog import select_dataset
from erpnext_ai_business_analyst.reports.qa import answer_from_approved_dataset, answer_from_general_analyst
from erpnext_ai_business_analyst.skills.base import Evidence, Finding, SkillResult, SkillStatus
from erpnext_ai_business_analyst.skills.registry import SkillRegistry
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


@frappe.whitelist()
def ask_question(question: str, report_dataset: str | None = None, report_filters: dict | None = None) -> dict:
    if not question or not question.strip():
        frappe.throw("Question is required")
    if isinstance(report_filters, str):
        report_filters = frappe.parse_json(report_filters)
    if not isinstance(report_filters, dict):
        report_filters = {}

    llm_client = OllamaClient()  # reads ollama_model/ollama_host from site_config
    embedding_client = OllamaEmbeddingClient()  # reads ollama_embedding_model/ollama_host

    tool_registry = ToolRegistry.get()
    skill_registry = SkillRegistry.get()
    report_answer = None
    if report_dataset:
        # A user's explicit report choice must not trigger an unrelated Skill first.
        result = InvestigationResult(status="ok")
        report_answer = answer_from_approved_dataset(question, tool_registry, llm_client, report_dataset, report_filters)
    else:
        # Explicit Skill phrases keep priority. A clear catalog report comes
        # next. For broader inventory questions, the general analyst may pick
        # only from the same approved report catalog before semantic Skills
        # are considered.
        explicit_skill = classify_question(question, skill_registry)
        auto_dataset = None if explicit_skill else select_dataset(question)
        general_report_answer = None
        if auto_dataset:
            result = InvestigationResult(status="ok")
            report_answer = answer_from_approved_dataset(question, tool_registry, llm_client, auto_dataset.name, report_filters)
        elif not explicit_skill:
            general_report_answer = answer_from_general_analyst(question, tool_registry, llm_client)
            if general_report_answer:
                result = InvestigationResult(status="ok")
                report_answer = general_report_answer
            else:
                result = run_investigation(
                    question=question,
                    tool_registry=tool_registry,
                    skill_registry=skill_registry,
                    llm_client=llm_client,
                    embedding_client=embedding_client,
                )
        else:
            result = run_investigation(
                question=question,
                tool_registry=tool_registry,
                skill_registry=skill_registry,
                llm_client=llm_client,
                embedding_client=embedding_client,
            )
        if not auto_dataset and not general_report_answer and result.category == "no_matching_skill" and not result.history:
            report_answer = answer_from_approved_dataset(question, tool_registry, llm_client, filters=report_filters)
    if report_answer:
        report_result = SkillResult(
            status=SkillStatus.OK,
            findings=[Finding(claim=report_answer.answer, confidence=1.0, supporting_evidence_ids=["ev-report"])],
            metrics={"dataset": report_answer.source_label, "record_count": report_answer.record_count},
            evidence=[Evidence("ev-report", f"report:{report_answer.source_label}", {"filters": report_answer.filters}, report_answer.records, report_answer.evidence_summary)],
        )
        result.history.append(InvestigationStep(skill_name=f"report.{report_answer.source_label}", inputs=report_answer.filters, result=report_result))
        result.hop_count = len(result.history)
    log_name = save_investigation_log(question, result)

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
        "report_answer": report_answer.answer if report_answer else None,
        "report_source": report_answer.source_label if report_answer else None,
        "report_record_count": report_answer.record_count if report_answer else None,
        "report_evidence_summary": report_answer.evidence_summary if report_answer else None,
        "report_records": report_answer.records if report_answer else [],
    }


@frappe.whitelist()
def get_recent_investigations(limit: int = 8) -> list[dict]:
    """Return a small, privacy-scoped list of the current user's investigations."""
    limit = max(1, min(cint(limit), 20))
    return frappe.get_all(
        "AI Investigation Log",
        filters={"owner": frappe.session.user},
        fields=["name", "question", "status", "timestamp"],
        order_by="modified desc",
        limit_page_length=limit,
    )


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
