"""
Tool: inventory.get_reorder_status

Generic reorder/pending-procurement status per Item+Warehouse, built on
standard ERPNext DocTypes only (Item Reorder, Item, Stock Ledger Entry,
Material Request, Purchase Order, Purchase Receipt).

Deliberately excludes Precision Mass-specific extensions (custom Critical
Stock Level field, D Work Order). A client-specific app can add those via
its own Tool registered under a different name (e.g.
"inventory.get_reorder_status_precision_mass") and, if desired, chain it
after this one in a Skill.
"""

from __future__ import annotations

import frappe

from erpnext_ai_business_analyst.tools.base import (
    QueryMeta,
    Tool,
    ToolParam,
    ToolResult,
    ToolStatus,
)

REQUIRED_READ_DOCTYPES = [
    "Item",
    "Stock Ledger Entry",
    "Material Request",
    "Purchase Order",
    "Purchase Receipt",
]


def _check_read_permission() -> str | None:
    """Coarse, role-level permission gate. Note: the underlying query is raw
    SQL joined across doctypes, so per-record (row-level) permission rules
    are NOT enforced here — only doctype-level read access. Flagged as a
    known limitation until a permission-query-condition layer is added."""
    for doctype in REQUIRED_READ_DOCTYPES:
        if not frappe.has_permission(doctype, "read"):
            return f"Missing read permission on '{doctype}'"
    return None


def _get_reorder_status(
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    below_rol_qty: bool = False,
    trigger_qty_only: bool = False,
) -> ToolResult:
    denied_reason = _check_read_permission()
    if denied_reason:
        return ToolResult(status=ToolStatus.ERROR, error=denied_reason, denied_reason=denied_reason)

    conditions = []
    values: dict = {}

    if item_code:
        conditions.append("ir.parent = %(item_code)s")
        values["item_code"] = item_code
    if warehouse:
        conditions.append("ir.warehouse = %(warehouse)s")
        values["warehouse"] = warehouse
    if item_group:
        conditions.append("item.item_group = %(item_group)s")
        values["item_group"] = item_group

    condition_str = (" AND " + " AND ".join(conditions)) if conditions else ""

    having_conditions = []
    if below_rol_qty:
        having_conditions.append("rol IS NOT NULL AND stock < rol")
    if trigger_qty_only:
        having_conditions.append("trigger_qty > 0")
    having_clause = ("HAVING " + " AND ".join(having_conditions)) if having_conditions else ""

    sql = f"""
        WITH latest_sle AS (
            SELECT
                item_code,
                warehouse,
                qty_after_transaction,
                ROW_NUMBER() OVER (
                    PARTITION BY item_code, warehouse
                    ORDER BY posting_datetime DESC, creation DESC
                ) AS rn
            FROM `tabStock Ledger Entry`
            WHERE docstatus = 1 AND is_cancelled = 0
        ),
        pending_pr AS (
            SELECT
                mri.item_code,
                mri.warehouse,
                SUM(GREATEST(mri.qty - mri.ordered_qty, 0)) AS pending_pr
            FROM `tabMaterial Request Item` mri
            INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
            WHERE mr.docstatus = 1
                AND mr.material_request_type = 'Purchase'
                AND mr.status NOT IN ('Stopped', 'Cancelled')
            GROUP BY mri.item_code, mri.warehouse
        ),
        pending_str AS (
            SELECT
                mri.item_code,
                mri.warehouse,
                SUM(GREATEST(mri.qty - mri.ordered_qty, 0)) AS pending_str
            FROM `tabMaterial Request Item` mri
            INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
            WHERE mr.docstatus = 1
                AND mr.material_request_type = 'Material Transfer'
                AND mr.status NOT IN ('Stopped', 'Cancelled')
            GROUP BY mri.item_code, mri.warehouse
        ),
        pr_received AS (
            SELECT
                purchase_order_item,
                SUM(qty) AS received_qty
            FROM `tabPurchase Receipt Item`
            WHERE docstatus = 1
            GROUP BY purchase_order_item
        ),
        pending_po AS (
            SELECT
                poi.item_code,
                poi.warehouse,
                SUM(GREATEST(poi.qty - COALESCE(prr.received_qty, 0), 0)) AS pending_po
            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
            LEFT JOIN pr_received prr ON prr.purchase_order_item = poi.name
            WHERE po.docstatus = 1
                AND po.status NOT IN ('Closed', 'Cancelled')
            GROUP BY poi.item_code, poi.warehouse
        ),
        base AS (
            SELECT
                ir.parent AS item_code,
                item.item_name AS item_name,
                ir.warehouse AS warehouse,
                item.item_group AS item_group,
                item.stock_uom AS uom,
                COALESCE(sle.qty_after_transaction, 0) AS stock,
                COALESCE(pr.pending_pr, 0) AS pending_pr,
                COALESCE(str.pending_str, 0) AS pending_str,
                COALESCE(po.pending_po, 0) AS pending_po,
                0 AS pending_wo,
                ir.warehouse_reorder_level AS rol,
                ir.warehouse_reorder_qty AS roq
            FROM `tabItem Reorder` ir
            INNER JOIN `tabItem` item ON item.name = ir.parent
            LEFT JOIN latest_sle sle
                ON sle.item_code = ir.parent AND sle.warehouse = ir.warehouse AND sle.rn = 1
            LEFT JOIN pending_pr pr ON pr.item_code = ir.parent AND pr.warehouse = ir.warehouse
            LEFT JOIN pending_str str ON str.item_code = ir.parent AND str.warehouse = ir.warehouse
            LEFT JOIN pending_po po ON po.item_code = ir.parent AND po.warehouse = ir.warehouse
            WHERE ir.warehouse IS NOT NULL AND ir.warehouse != ''
                {condition_str}
        )
        SELECT
            item_code, item_name, warehouse, item_group, uom,
            stock, pending_pr, pending_str, pending_po, pending_wo,
            (stock + pending_pr + pending_str + pending_po + pending_wo) AS projected_qty,
            rol, roq,
            CASE
                WHEN (stock + pending_pr + pending_str + pending_po + pending_wo) < COALESCE(rol, 0)
                THEN GREATEST(COALESCE(rol, 0) - (stock + pending_pr + pending_str + pending_po + pending_wo), COALESCE(roq, 0))
                ELSE 0
            END AS trigger_qty
        FROM base
        {having_clause}
        ORDER BY item_name, warehouse
    """

    data = frappe.db.sql(sql, values, as_dict=True)

    query_meta = QueryMeta(
        doctype="Item Reorder",
        filters={
            "item_code": item_code,
            "warehouse": warehouse,
            "item_group": item_group,
            "below_rol_qty": below_rol_qty,
            "trigger_qty_only": trigger_qty_only,
        },
        fields=list(data[0].keys()) if data else [],
        row_count=len(data),
    )

    return ToolResult(status=ToolStatus.OK, data=data, query_meta=query_meta)


TOOL = Tool(
    name="inventory.get_reorder_status",
    description=(
        "Reorder/pending-procurement status per Item+Warehouse: current stock, "
        "pending PR/STR/PO, projected qty, and trigger qty against ROL/ROQ."
    ),
    params=[
        ToolParam("item_code", "str", required=False),
        ToolParam("warehouse", "str", required=False),
        ToolParam("item_group", "str", required=False),
        ToolParam("below_rol_qty", "bool", required=False, default=False),
        ToolParam("trigger_qty_only", "bool", required=False, default=False),
    ],
    func=_get_reorder_status,
)