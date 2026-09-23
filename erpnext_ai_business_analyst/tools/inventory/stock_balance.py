"""Read-only current stock, reservation, and valuation data by item and warehouse."""

from __future__ import annotations

import frappe

from erpnext_ai_business_analyst.tools.base import QueryMeta, Tool, ToolParam, ToolResult, ToolStatus


def _get_stock_balance(
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
) -> ToolResult:
    for doctype in ("Bin", "Item"):
        if not frappe.has_permission(doctype, "read"):
            return ToolResult(status=ToolStatus.ERROR, error=f"Missing read permission on '{doctype}'")

    conditions = []
    values: dict[str, str] = {}
    if item_code:
        conditions.append("b.item_code = %(item_code)s")
        values["item_code"] = item_code
    if warehouse:
        conditions.append("b.warehouse = %(warehouse)s")
        values["warehouse"] = warehouse
    if item_group:
        conditions.append("i.item_group = %(item_group)s")
        values["item_group"] = item_group
    filters = (" AND " + " AND ".join(conditions)) if conditions else ""

    data = frappe.db.sql(f"""
        SELECT b.item_code, i.item_name, i.item_group, i.stock_uom AS uom, b.warehouse,
            COALESCE(b.actual_qty, 0) AS actual_qty,
            COALESCE(b.reserved_qty, 0) AS reserved_qty,
            COALESCE(b.ordered_qty, 0) AS ordered_qty,
            COALESCE(b.planned_qty, 0) AS planned_qty,
            COALESCE(b.indented_qty, 0) AS indented_qty,
            COALESCE(b.projected_qty, 0) AS projected_qty,
            COALESCE(b.valuation_rate, 0) AS valuation_rate,
            COALESCE(b.stock_value, 0) AS stock_value
        FROM `tabBin` b
        INNER JOIN `tabItem` i ON i.name = b.item_code
        WHERE (COALESCE(b.actual_qty, 0) != 0 OR COALESCE(b.reserved_qty, 0) != 0
            OR COALESCE(b.ordered_qty, 0) != 0 OR COALESCE(b.planned_qty, 0) != 0){filters}
        ORDER BY i.item_name, b.warehouse
    """, values, as_dict=True)

    return ToolResult(
        status=ToolStatus.OK,
        data=data,
        query_meta=QueryMeta(
            doctype="Bin", filters={"item_code": item_code, "warehouse": warehouse, "item_group": item_group},
            fields=list(data[0].keys()) if data else [], row_count=len(data),
        ),
    )


TOOL = Tool(
    name="inventory.get_stock_balance",
    description="Current item and warehouse stock: available, reserved, incoming, projected quantity, and stock value.",
    params=[
        ToolParam("item_code", "str", required=False),
        ToolParam("warehouse", "str", required=False),
        ToolParam("item_group", "str", required=False),
    ],
    func=_get_stock_balance,
)
