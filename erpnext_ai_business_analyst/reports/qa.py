"""Safe report Q&A: runs only catalogued datasets and summarizes only returned rows."""

from __future__ import annotations

import json
from dataclasses import dataclass

from erpnext_ai_business_analyst.agent.llm.base import LLMClient
from erpnext_ai_business_analyst.reports.catalog import DATASETS, ApprovedDataset, get_dataset, select_dataset
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry

MAX_RECORDS_FOR_SUMMARY = 50
MAX_GENERAL_ANALYST_DATASETS = 3


@dataclass(frozen=True)
class ReportAnswer:
    answer: str
    source_label: str
    record_count: int
    evidence_summary: str
    records: list[dict]
    filters: dict


def is_inventory_question(question: str) -> bool:
    """Avoid asking the general router to handle clearly unrelated chat."""
    inventory_words = {
        "inventory", "stock", "item", "warehouse", "supplier", "purchase", "sales",
        "batch", "reorder", "consumption", "material", "demand", "order", "expiry",
        "shortage", "valuation", "delivery", "receipt",
    }
    words = set(question.lower().replace("-", " ").replace("/", " ").split())
    return bool(words & inventory_words)


def select_general_analyst_datasets(question: str, llm_client: LLMClient) -> list[ApprovedDataset]:
    """Let the LLM choose from the fixed dataset catalog, never arbitrary data."""
    catalog = "\n".join(f"- {dataset.name}: {dataset.description}" for dataset in DATASETS)
    system_prompt = (
        "You route ERPNext inventory questions to approved read-only datasets. "
        "Choose up to three dataset names from the supplied catalog only when combining them would improve the answer. "
        "Return an empty list for questions that cannot be answered from inventory data. "
        'Respond with only JSON: {"datasets": ["dataset_name"]}.'
    )
    user_prompt = f"Question: {question}\n\nApproved dataset catalog:\n{catalog}"
    try:
        response = llm_client.complete(system_prompt, user_prompt, max_tokens=220).strip()
        if response.startswith("```"):
            response = response.strip("`").removeprefix("json").strip()
        names = json.loads(response).get("datasets", [])
    except (AttributeError, json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(names, list):
        return []

    selected: list[ApprovedDataset] = []
    for name in names:
        dataset = get_dataset(name) if isinstance(name, str) else None
        if dataset and dataset not in selected:
            selected.append(dataset)
        if len(selected) == MAX_GENERAL_ANALYST_DATASETS:
            break
    return selected


def _run_dataset(dataset: ApprovedDataset, tool_registry: ToolRegistry, filters: dict | None = None):
    safe_filters = {
        key: value for key, value in (filters or {}).items()
        if key in dataset.allowed_filters and value not in (None, "")
    }
    inputs = {**dataset.default_inputs, **safe_filters}
    if dataset.tool_name == "inventory.run_builtin_report":
        inputs = {**dataset.default_inputs, "filters": safe_filters}
    return tool_registry.get_tool(dataset.tool_name)(**inputs), safe_filters


def _record_counts(result) -> tuple[int, int, bool]:
    """Return displayed rows, total matching rows, and whether data was limited."""
    displayed = len(result.data or [])
    meta = result.query_meta
    total = meta.total_row_count if meta and meta.total_row_count is not None else displayed
    return displayed, total, bool(meta and meta.truncated)


def answer_from_approved_dataset(question: str, tool_registry: ToolRegistry, llm_client: LLMClient, dataset_name: str | None = None, filters: dict | None = None) -> ReportAnswer | None:
    dataset = get_dataset(dataset_name) if dataset_name else select_dataset(question)
    if dataset is None:
        return None
    result, safe_filters = _run_dataset(dataset, tool_registry, filters)
    if result.status != ToolStatus.OK:
        return ReportAnswer("I could not read the approved ERP data source for this question.", dataset.label, 0, result.error or "Data source unavailable", [], safe_filters)
    if not result.data:
        return ReportAnswer(f"No records were found in {dataset.label} for this question.", dataset.label, 0, "No matching records", [], safe_filters)
    displayed_count, total_count, truncated = _record_counts(result)
    records = result.data[:MAX_RECORDS_FOR_SUMMARY]
    system_prompt = (
        "You are an ERPNext business-data assistant. Answer only from the supplied approved report data. "
        "Do not invent values, assume missing facts, or give unrelated advice. Be concise, mention key numbers, "
        "and say when the data cannot answer the question."
    )
    user_prompt = (
        f"Question: {question}\n\nApproved dataset: {dataset.label}\nDescription: {dataset.description}\n"
        f"Returned records (showing {len(records)} of {total_count}):\n{json.dumps(records, default=str)}"
    )
    try:
        answer = llm_client.complete(system_prompt, user_prompt, max_tokens=350).strip()
    except Exception:
        answer = f"{total_count} records were found in {dataset.label}. Open the evidence to review the returned data."
    evidence_summary = f"{total_count} record(s) returned from approved dataset: {dataset.label}"
    if truncated:
        evidence_summary += f". Showing the first {displayed_count} rows only."
    return ReportAnswer(answer, dataset.label, total_count, evidence_summary, records, safe_filters)


def answer_from_general_analyst(question: str, tool_registry: ToolRegistry, llm_client: LLMClient) -> ReportAnswer | None:
    """Answer broad inventory questions by combining LLM-selected approved datasets."""
    if not is_inventory_question(question):
        return None
    datasets = select_general_analyst_datasets(question, llm_client)
    if not datasets:
        return None

    sources = []
    display_records = []
    total_records = 0
    for dataset in datasets:
        result, safe_filters = _run_dataset(dataset, tool_registry)
        if result.status != ToolStatus.OK:
            continue
        rows = result.data or []
        _displayed_count, source_total, _truncated = _record_counts(result)
        total_records += source_total
        sources.append((dataset, rows, safe_filters, source_total, _truncated))
        for row in rows:
            if len(display_records) == MAX_RECORDS_FOR_SUMMARY:
                break
            display_records.append({"source": dataset.label, **row} if isinstance(row, dict) else {"source": dataset.label, "value": row})

    dataset_labels = " + ".join(dataset.label for dataset in datasets)
    source_label = f"AI Business Analysis — {dataset_labels}"
    if not sources or not total_records:
        return ReportAnswer(
            f"No records were found in the approved ERP data source(s) selected for this question: {source_label}.",
            source_label, 0, "No matching records", [], {},
        )

    records_per_source = max(1, MAX_RECORDS_FOR_SUMMARY // len(sources))
    source_data = [
        {
            "dataset": dataset.label,
            "matching_record_count": source_total,
            "data_limited": truncated,
            "records": rows[:records_per_source],
        }
        for dataset, rows, _filters, source_total, truncated in sources
    ]
    system_prompt = (
        "You are an ERPNext inventory analyst. Answer only from the supplied approved ERP data. "
        "Do not invent facts, calculate from missing values, or claim a source says something it does not. "
        "Give a concise BI-style answer. Lead with a one-sentence summary, then provide up to three "
        "prioritized insights. For each insight, state the risk or opportunity and one recommended action. "
        "State clearly when the returned data is insufficient."
    )
    user_prompt = f"Question: {question}\n\nApproved data returned:\n{json.dumps(source_data, default=str)}"
    try:
        answer = llm_client.complete(system_prompt, user_prompt, max_tokens=400).strip()
    except Exception:
        answer = f"{total_records} records were found across {source_label}. Open the returned rows to review the data."
    filters = {dataset.name: safe_filters for dataset, _rows, safe_filters, _total, _truncated in sources}
    return ReportAnswer(
        answer, source_label, total_records,
        f"{total_records} record(s) returned from approved dataset(s): {dataset_labels}",
        display_records, filters,
    )
