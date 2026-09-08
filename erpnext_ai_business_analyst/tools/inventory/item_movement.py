"""
Tool: inventory.get_item_movement

Generic last-movement-date and consumption-window stats per Item+Warehouse,
built on standard ERPNext DocTypes only (Bin, Item, Stock Ledger Entry).

Base entity set is `tabBin` (all item+warehouse combos with a stock
record) rather than Item Reorder, so this covers items with no reorder
config too — needed for Dead Stock / Slow-Moving / Overstock, which must
look at all stocked items, not just reorder-managed ones.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, nowdate

from erpnext_ai_business_analyst.tools.base import (
    QueryMeta,
    Tool,
    ToolParam,
    ToolResult,
    ToolStatus,
)

REQUIRED_READ_DOCTYPES = ["Bin", "Item", "Stock Ledger Entry"]


def _check_read_permission() -> str | None:
    for doctype in REQUIRED_READ_DOCTYPES:
        if not frappe.has_permission(doctype, "read"):
            return f"Missing read permission on '{doctype}'"
    return None


def _get_item_movement(
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    window_days: int = 90,
    min_days_since_movement: int | None = None,
) -> ToolResult:
    denied_reason = _check_read_permission()
    if denied_reason:
        return ToolResult(status=ToolStatus.ERROR, error=denied_reason, denied_reason=denied_reason)

    conditions = []
    values: dict = {"window_start": add_days(nowdate(), -window_days)}

    if item_code:
        conditions.append("b.item_code = %(item_code)s")
        values["item_code"] = item_code
    if warehouse:
        conditions.append("b.warehouse = %(warehouse)s")
        values["warehouse"] = warehouse
    if item_group:
        conditions.append("item.item_group = %(item_group)s")
        values["item_group"] = item_group

    condition_str = (" AND " + " AND ".join(conditions)) if conditions else ""

    having_clause = ""
    if min_days_since_movement is not None:
        having_clause = "HAVING days_since_last_movement >= %(min_days_since_movement)s OR days_since_last_movement IS NULL"
        values["min_days_since_movement"] = min_days_since_movement

    sql = f"""
        WITH movement AS (
            SELECT
                item_code,
                warehouse,
                MAX(posting_datetime) AS last_movement_date,
                SUM(CASE WHEN posting_datetime >= %(window_start)s AND actual_qty < 0
                    THEN ABS(actual_qty) ELSE 0 END) AS qty_out_in_window,
                SUM(CASE WHEN posting_datetime >= %(window_start)s AND actual_qty > 0
                    THEN actual_qty ELSE 0 END) AS qty_in_in_window,
                SUM(CASE WHEN posting_datetime >= %(window_start)s THEN 1 ELSE 0 END) AS movement_count_in_window
            FROM `tabStock Ledger Entry`
            WHERE docstatus = 1 AND is_cancelled = 0
            GROUP BY item_code, warehouse
        )
        SELECT
            b.item_code,
            item.item_name,
            b.warehouse,
            item.item_group,
            item.stock_uom AS uom,
            b.actual_qty AS stock,
            m.last_movement_date,
            DATEDIFF(NOW(), m.last_movement_date) AS days_since_last_movement,
            COALESCE(m.qty_out_in_window, 0) AS qty_out_in_window,
            COALESCE(m.qty_in_in_window, 0) AS qty_in_in_window,
            COALESCE(m.movement_count_in_window, 0) AS movement_count_in_window
        FROM `tabBin` b
        INNER JOIN `tabItem` item ON item.name = b.item_code
        LEFT JOIN movement m ON m.item_code = b.item_code AND m.warehouse = b.warehouse
        WHERE b.actual_qty != 0
            {condition_str}
        {having_clause}
        ORDER BY item.item_name, b.warehouse
    """

    data = frappe.db.sql(sql, values, as_dict=True)

    query_meta = QueryMeta(
        doctype="Bin",
        filters={
            "item_code": item_code,
            "warehouse": warehouse,
            "item_group": item_group,
            "window_days": window_days,
            "min_days_since_movement": min_days_since_movement,
        },
        fields=list(data[0].keys()) if data else [],
        row_count=len(data),
    )

    return ToolResult(status=ToolStatus.OK, data=data, query_meta=query_meta)


TOOL = Tool(
    name="inventory.get_item_movement",
    description=(
        "Last-movement-date and consumption-window stats per Item+Warehouse: "
        "current stock, days since last movement, qty in/out within a rolling window."
    ),
    params=[
        ToolParam("item_code", "str", required=False),
        ToolParam("warehouse", "str", required=False),
        ToolParam("item_group", "str", required=False),
        ToolParam("window_days", "int", required=False, default=90),
        ToolParam("min_days_since_movement", "int", required=False),
    ],
    func=_get_item_movement,
)