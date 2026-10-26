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
    "Warehouse Wise Stock Balance",
    "Stock Projected Qty",
    "Item Shortage Report",
    "Batch Item Expiry Status",
    "Item Wise Consumption",
    "Stock and Account Value Comparison",
    "Purchase Order Trends",
    "Sales Order Trends",
}

# Query reports return every matching row. Keep a bounded result in the AI
# response so a broad report cannot fill the web response or the model context.
# The original count remains in QueryMeta, so callers never mistake this for a
# complete result set.
MAX_REPORT_ROWS = 250

# These reports normally receive their defaults from ERPNext's Desk report
# UI. The AI runner calls them server-side, so it must provide the same safe
# defaults itself. Users cannot supply arbitrary report filters through chat.
REPORT_DEFAULT_FILTERS = {
    "Purchase Order Trends": {"based_on": "Item", "period": "Monthly", "period_based_on": "posting_date"},
    "Sales Order Trends": {"based_on": "Item", "period": "Monthly"},
}

COMPANY_CONTEXT_REPORTS = {
    "Stock Balance",
    "Stock Ledger",
    "Stock Ageing",
    "Purchase Order Analysis",
    "Sales Order Analysis",
    "Warehouse Wise Stock Balance",
    "Stock Projected Qty",
    "Item Shortage Report",
    "Stock and Account Value Comparison",
    "Purchase Order Trends",
    "Sales Order Trends",
}


def _get_default_company() -> str | None:
    """Use the same company defaults ERPNext's Desk report UI uses."""
    return frappe.defaults.get_user_default("Company") or frappe.defaults.get_default("company")


def _run_builtin_report(report_name: str, filters: dict | None = None) -> ToolResult:
    if report_name not in APPROVED_REPORTS:
        return ToolResult(status=ToolStatus.ERROR, error="This ERPNext report is not approved for AI analysis.")
    report_filters = {**REPORT_DEFAULT_FILTERS.get(report_name, {}), **dict(filters or {})}
    if report_name == "Stock and Account Value Comparison":
        report_filters.setdefault("as_on_date", nowdate())
    if report_name in COMPANY_CONTEXT_REPORTS and not report_filters.get("company"):
        if company := _get_default_company():
            report_filters["company"] = company
    row_filters = {key: report_filters.pop(key) for key in ("supplier", "customer") if report_filters.get(key)}
    report_filters.setdefault("from_date", add_days(nowdate(), -90))
    report_filters.setdefault("to_date", nowdate())
    if report_filters.get("item_code"):
        report_filters["item_code"] = [report_filters["item_code"]]
    # Most stock reports accept one or more warehouses. Sales Order Analysis
    # is different: it binds warehouse with SQL "=" and therefore requires a
    # scalar value.
    if report_filters.get("warehouse") and report_name != "Sales Order Analysis":
        report_filters["warehouse"] = [report_filters["warehouse"]]
    try:
        output = run(report_name, filters=report_filters)
    except frappe.PermissionError as error:
        return ToolResult(status=ToolStatus.ERROR, error=str(error), denied_reason=str(error))
    except Exception as error:
        return ToolResult(status=ToolStatus.ERROR, error=str(error))
    data = output.get("result") or []
    for field, value in row_filters.items():
        data = [row for row in data if isinstance(row, dict) and row.get(field) == value]
    report_filters.update(row_filters)
    total_row_count = len(data)
    truncated = total_row_count > MAX_REPORT_ROWS
    data = data[:MAX_REPORT_ROWS]
    return ToolResult(status=ToolStatus.OK, data=data, query_meta=QueryMeta(
        doctype=f"Report: {report_name}", filters=report_filters,
        fields=list(data[0].keys()) if data and isinstance(data[0], dict) else [], row_count=len(data),
        total_row_count=total_row_count, truncated=truncated,
    ))


TOOL = Tool(
    name="inventory.run_builtin_report",
    description="Runs only approved standard ERPNext reports with the current user's report permissions.",
    params=[ToolParam("report_name", "str"), ToolParam("filters", "dict", required=False, default={})],
    func=_run_builtin_report,
)
