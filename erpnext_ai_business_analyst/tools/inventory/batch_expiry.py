"""Read-only list of ERPNext batches approaching or past expiry."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate

from erpnext_ai_business_analyst.tools.base import QueryMeta, Tool, ToolParam, ToolResult, ToolStatus


def _get_batch_expiry(item_code: str | None = None, days_ahead: int = 90) -> ToolResult:
    for doctype in ("Batch", "Item"):
        if not frappe.has_permission(doctype, "read"):
            return ToolResult(status=ToolStatus.ERROR, error=f"Missing read permission on '{doctype}'")
    values = {"cutoff": add_days(nowdate(), days_ahead)}
    condition = ""
    if item_code:
        condition = " AND b.item = %(item_code)s"
        values["item_code"] = item_code
    data = frappe.db.sql(f"""
        SELECT b.name AS batch, b.item AS item_code, i.item_name, b.expiry_date,
            DATEDIFF(b.expiry_date, CURDATE()) AS days_to_expiry
        FROM `tabBatch` b
        INNER JOIN `tabItem` i ON i.name = b.item
        WHERE b.disabled = 0 AND b.expiry_date IS NOT NULL AND b.expiry_date <= %(cutoff)s{condition}
        ORDER BY b.expiry_date, i.item_name
    """, values, as_dict=True)
    return ToolResult(status=ToolStatus.OK, data=data, query_meta=QueryMeta(
        doctype="Batch", filters={"item_code": item_code, "days_ahead": days_ahead},
        fields=list(data[0].keys()) if data else [], row_count=len(data),
    ))


TOOL = Tool(
    name="inventory.get_batch_expiry",
    description="Batches with an expiry date within a selected number of days; does not infer quantity by batch.",
    params=[ToolParam("item_code", "str", required=False), ToolParam("days_ahead", "int", required=False, default=90)],
    func=_get_batch_expiry,
)
