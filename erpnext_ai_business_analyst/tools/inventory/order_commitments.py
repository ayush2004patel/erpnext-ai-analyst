"""Read-only open purchase supply and sales-demand commitments."""

from __future__ import annotations

import frappe

from erpnext_ai_business_analyst.tools.base import QueryMeta, Tool, ToolParam, ToolResult, ToolStatus


def _get_order_commitments(item_code: str | None = None, warehouse: str | None = None) -> ToolResult:
    required = ("Purchase Order", "Sales Order", "Item")
    for doctype in required:
        if not frappe.has_permission(doctype, "read"):
            return ToolResult(status=ToolStatus.ERROR, error=f"Missing read permission on '{doctype}'")

    conditions, values = [], {}
    if item_code:
        conditions.append("oi.item_code = %(item_code)s")
        values["item_code"] = item_code
    if warehouse:
        conditions.append("oi.warehouse = %(warehouse)s")
        values["warehouse"] = warehouse
    filters = (" AND " + " AND ".join(conditions)) if conditions else ""

    purchase_rows = frappe.db.sql(f"""
        SELECT 'purchase' AS commitment_type, po.name AS order_name, poi.item_code, i.item_name,
            poi.warehouse, poi.schedule_date, (poi.qty - COALESCE(poi.received_qty, 0)) AS open_qty,
            poi.qty AS ordered_qty
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
        INNER JOIN `tabItem` i ON i.name = poi.item_code
        WHERE po.docstatus = 1 AND po.status NOT IN ('Closed', 'Cancelled')
            AND (poi.qty - COALESCE(poi.received_qty, 0)) > 0{filters}
    """, values, as_dict=True)
    sales_rows = frappe.db.sql(f"""
        SELECT 'sales' AS commitment_type, so.name AS order_name, soi.item_code, i.item_name,
            soi.warehouse, soi.delivery_date AS schedule_date, (soi.qty - COALESCE(soi.delivered_qty, 0)) AS open_qty,
            soi.qty AS ordered_qty
        FROM `tabSales Order Item` soi
        INNER JOIN `tabSales Order` so ON so.name = soi.parent
        INNER JOIN `tabItem` i ON i.name = soi.item_code
        WHERE so.docstatus = 1 AND so.status NOT IN ('Closed', 'Cancelled')
            AND (soi.qty - COALESCE(soi.delivered_qty, 0)) > 0{filters.replace('oi.', 'soi.')}
    """, values, as_dict=True)
    data = purchase_rows + sales_rows
    return ToolResult(status=ToolStatus.OK, data=data, query_meta=QueryMeta(
        doctype="Purchase Order / Sales Order", filters={"item_code": item_code, "warehouse": warehouse},
        fields=list(data[0].keys()) if data else [], row_count=len(data),
    ))


TOOL = Tool(
    name="inventory.get_order_commitments",
    description="Open purchase-order supply and outstanding sales-order commitments by item and warehouse.",
    params=[ToolParam("item_code", "str", required=False), ToolParam("warehouse", "str", required=False)],
    func=_get_order_commitments,
)
