"""Safe report Q&A: runs only catalogued datasets and summarizes only returned rows."""

from __future__ import annotations

import json
from dataclasses import dataclass

from erpnext_ai_business_analyst.agent.llm.base import LLMClient
from erpnext_ai_business_analyst.reports.catalog import get_dataset, select_dataset
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry

MAX_RECORDS_FOR_SUMMARY = 50


@dataclass(frozen=True)
class ReportAnswer:
    answer: str
    source_label: str
    record_count: int
    evidence_summary: str
    records: list[dict]
    filters: dict


def answer_from_approved_dataset(question: str, tool_registry: ToolRegistry, llm_client: LLMClient, dataset_name: str | None = None, filters: dict | None = None) -> ReportAnswer | None:
    dataset = get_dataset(dataset_name) if dataset_name else select_dataset(question)
    if dataset is None:
        return None
    safe_filters = {key: value for key, value in (filters or {}).items() if key in dataset.allowed_filters and value not in (None, "")}
    inputs = {**dataset.default_inputs, **safe_filters}
    if dataset.tool_name == "inventory.run_builtin_report":
        inputs = {**dataset.default_inputs, "filters": safe_filters}
    result = tool_registry.get_tool(dataset.tool_name)(**inputs)
    if result.status != ToolStatus.OK:
        return ReportAnswer("I could not read the approved ERP data source for this question.", dataset.label, 0, result.error or "Data source unavailable", [], safe_filters)
    if not result.data:
        return ReportAnswer(f"No records were found in {dataset.label} for this question.", dataset.label, 0, "No matching records", [], safe_filters)
    records = result.data[:MAX_RECORDS_FOR_SUMMARY]
    system_prompt = (
        "You are an ERPNext business-data assistant. Answer only from the supplied approved report data. "
        "Do not invent values, assume missing facts, or give unrelated advice. Be concise, mention key numbers, "
        "and say when the data cannot answer the question."
    )
    user_prompt = (
        f"Question: {question}\n\nApproved dataset: {dataset.label}\nDescription: {dataset.description}\n"
        f"Returned records (showing {len(records)} of {len(result.data)}):\n{json.dumps(records, default=str)}"
    )
    try:
        answer = llm_client.complete(system_prompt, user_prompt, max_tokens=350).strip()
    except Exception:
        answer = f"{len(result.data)} records were found in {dataset.label}. Open the evidence to review the returned data."
    return ReportAnswer(answer, dataset.label, len(result.data), f"{len(result.data)} record(s) returned from approved dataset: {dataset.label}", records, safe_filters)
