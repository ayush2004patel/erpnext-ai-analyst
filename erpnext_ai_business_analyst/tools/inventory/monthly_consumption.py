"""Read-only monthly stock-consumption history for demand-pattern analysis."""

from __future__ import annotations

import frappe
from frappe.utils import add_months, nowdate

from erpnext_ai_business_analyst.tools.base import QueryMeta, Tool, ToolParam, ToolResult, ToolStatus


def _get_monthly_consumption(
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    months: int = 6,
) -> ToolResult:
    for doctype in ("Stock Ledger Entry", "Item"):
        if not frappe.has_permission(doctype, "read"):
            return ToolResult(status=ToolStatus.ERROR, error=f"Missing read permission on '{doctype}'")
    conditions, values = [], {"start_date": add_months(nowdate(), -months)}
    if item_code:
        conditions.append("sle.item_code = %(item_code)s")
        values["item_code"] = item_code
    if warehouse:
        conditions.append("sle.warehouse = %(warehouse)s")
        values["warehouse"] = warehouse
    if item_group:
        conditions.append("item.item_group = %(item_group)s")
        values["item_group"] = item_group
    filters = (" AND " + " AND ".join(conditions)) if conditions else ""
    data = frappe.db.sql(f"""
        SELECT sle.item_code, item.item_name, sle.warehouse,
            DATE_FORMAT(sle.posting_date, '%%Y-%%m') AS month,
            SUM(ABS(sle.actual_qty)) AS qty_out
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        WHERE sle.docstatus = 1 AND sle.is_cancelled = 0 AND sle.actual_qty < 0
            AND sle.posting_date >= %(start_date)s{filters}
        GROUP BY sle.item_code, item.item_name, sle.warehouse, DATE_FORMAT(sle.posting_date, '%%Y-%%m')
        ORDER BY sle.item_code, sle.warehouse, month
    """, values, as_dict=True)
    return ToolResult(status=ToolStatus.OK, data=data, query_meta=QueryMeta(
        doctype="Stock Ledger Entry", filters={"item_code": item_code, "warehouse": warehouse, "item_group": item_group, "months": months},
        fields=list(data[0].keys()) if data else [], row_count=len(data),
    ))


TOOL = Tool(
    name="inventory.get_monthly_consumption",
    description="Monthly outgoing stock quantities by item and warehouse for demand-pattern analysis.",
    params=[
        ToolParam("item_code", "str", required=False),
        ToolParam("warehouse", "str", required=False),
        ToolParam("item_group", "str", required=False),
        ToolParam("months", "int", required=False, default=6),
    ],
    func=_get_monthly_consumption,
)
