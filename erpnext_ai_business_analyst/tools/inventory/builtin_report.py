"""Safe runner for a small, explicit allowlist of standard ERPNext reports."""

from __future__ import annotations

import frappe
from frappe.desk.query_report import run
from frappe.utils import add_days, nowdate

from erpnext_ai_business_analyst.tools.base import QueryMeta, Tool, ToolParam, ToolResult, ToolStatus

APPROVED_REPORTS = {
    "Stock Balance",
    "Stock Ledger",
    "Stock Ageing",
    "Purchase Order Analysis",
    "Sales Order Analysis",
}


def _run_builtin_report(report_name: str, filters: dict | None = None) -> ToolResult:
    if report_name not in APPROVED_REPORTS:
        return ToolResult(status=ToolStatus.ERROR, error="This ERPNext report is not approved for AI analysis.")
    report_filters = dict(filters or {})
    row_filters = {key: report_filters.pop(key) for key in ("supplier", "customer") if report_filters.get(key)}
    report_filters.setdefault("from_date", add_days(nowdate(), -90))
    report_filters.setdefault("to_date", nowdate())
    if report_filters.get("item_code"):
        report_filters["item_code"] = [report_filters["item_code"]]
    if report_filters.get("warehouse"):
        report_filters["warehouse"] = [report_filters["warehouse"]]
    try:
        output = run(report_name, filters=report_filters)
    except frappe.PermissionError as error:
        return ToolResult(status=ToolStatus.ERROR, error=str(error), denied_reason=str(error))
    data = output.get("result") or []
    for field, value in row_filters.items():
        data = [row for row in data if isinstance(row, dict) and row.get(field) == value]
    report_filters.update(row_filters)
    return ToolResult(status=ToolStatus.OK, data=data, query_meta=QueryMeta(
        doctype=f"Report: {report_name}", filters=report_filters,
        fields=list(data[0].keys()) if data and isinstance(data[0], dict) else [], row_count=len(data),
    ))


TOOL = Tool(
    name="inventory.run_builtin_report",
    description="Runs only approved standard ERPNext reports with the current user's report permissions.",
    params=[ToolParam("report_name", "str"), ToolParam("filters", "dict", required=False, default={})],
    func=_run_builtin_report,
)
