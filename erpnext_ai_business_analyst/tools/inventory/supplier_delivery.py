"""Read-only historical purchase-order delivery performance by supplier."""

from __future__ import annotations

import frappe

from erpnext_ai_business_analyst.tools.base import QueryMeta, Tool, ToolParam, ToolResult, ToolStatus


def _get_supplier_delivery_performance(supplier: str | None = None, item_code: str | None = None) -> ToolResult:
    for doctype in ("Purchase Order", "Purchase Receipt", "Item"):
        if not frappe.has_permission(doctype, "read"):
            return ToolResult(status=ToolStatus.ERROR, error=f"Missing read permission on '{doctype}'")
    conditions, values = [], {}
    if supplier:
        conditions.append("po.supplier = %(supplier)s")
        values["supplier"] = supplier
    if item_code:
        conditions.append("poi.item_code = %(item_code)s")
        values["item_code"] = item_code
    filters = (" AND " + " AND ".join(conditions)) if conditions else ""
    data = frappe.db.sql(f"""
        SELECT po.supplier, po.name AS purchase_order, poi.item_code, item.item_name,
            poi.schedule_date, MAX(pr.posting_date) AS received_date,
            DATEDIFF(MAX(pr.posting_date), poi.schedule_date) AS delay_days
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
        INNER JOIN `tabItem` item ON item.name = poi.item_code
        INNER JOIN `tabPurchase Receipt Item` pri ON pri.purchase_order_item = poi.name
        INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent AND pr.docstatus = 1
        WHERE po.docstatus = 1{filters}
        GROUP BY po.supplier, po.name, poi.name, poi.item_code, item.item_name, poi.schedule_date
        ORDER BY po.supplier, received_date DESC
    """, values, as_dict=True)
    return ToolResult(status=ToolStatus.OK, data=data, query_meta=QueryMeta(
        doctype="Purchase Order / Purchase Receipt", filters={"supplier": supplier, "item_code": item_code},
        fields=list(data[0].keys()) if data else [], row_count=len(data),
    ))


TOOL = Tool(
    name="inventory.get_supplier_delivery_performance",
    description="Historical purchase-order delivery dates and delay days by supplier.",
    params=[ToolParam("supplier", "str", required=False), ToolParam("item_code", "str", required=False)],
    func=_get_supplier_delivery_performance,
)
