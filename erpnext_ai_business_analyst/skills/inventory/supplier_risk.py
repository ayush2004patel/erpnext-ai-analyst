"""Supplier delay and purchase-order risk skills."""

from __future__ import annotations

from collections import defaultdict

from frappe.utils import getdate, nowdate

from erpnext_ai_business_analyst.skills.base import Evidence, Finding, Skill, SkillParam, SkillResult, SkillStatus
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


def _evidence(result, evidence_id, tool_name, summary):
    return Evidence(evidence_id, tool_name, vars(result.query_meta) if result.query_meta else {}, result.data, summary)


def _overdue_purchase_orders(tool_registry, item_code=None, warehouse=None):
    result = tool_registry.get_tool("inventory.get_order_commitments")(item_code=item_code, warehouse=warehouse)
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    today = getdate(nowdate())
    rows = [row for row in result.data if row["commitment_type"] == "purchase" and row["schedule_date"] and getdate(row["schedule_date"]) < today]
    rows.sort(key=lambda row: row["schedule_date"])
    evidence = _evidence(result, "ev-order-commitments", "inventory.get_order_commitments", f"{len(rows)} overdue open purchase-order line(s)")
    findings = [Finding(
        claim=(f"Purchase order {row['order_name']} from {row['supplier']} is overdue: {row['open_qty']:.0f} of "
               f"{row['item_code']} ({row['item_name']}) was due on {row['schedule_date']} for {row['warehouse']}."),
        confidence=0.95, supporting_evidence_ids=[evidence.id],
    ) for row in rows]
    return SkillResult(SkillStatus.OK if findings else SkillStatus.NO_DATA, findings, {"overdue_purchase_order_line_count": len(findings)}, [evidence])


def _supplier_delivery_risk(tool_registry, supplier=None, item_code=None):
    result = tool_registry.get_tool("inventory.get_supplier_delivery_performance")(supplier=supplier, item_code=item_code)
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    by_supplier = defaultdict(list)
    for row in result.data:
        by_supplier[row["supplier"]].append(row["delay_days"])
    records, findings = [], []
    for supplier_name, delays in by_supplier.items():
        average_delay = sum(delays) / len(delays)
        late_count = sum(delay > 0 for delay in delays)
        if average_delay <= 0:
            continue
        records.append({"supplier": supplier_name, "average_delay_days": average_delay, "late_delivery_count": late_count, "delivery_count": len(delays)})
        findings.append(Finding(
            claim=(f"{supplier_name}: average delivery delay of {average_delay:.1f} days across {len(delays)} received purchase-order lines "
                   f"({late_count} delivered late)."),
            confidence=0.9 if average_delay >= 7 else 0.75, supporting_evidence_ids=["ev-supplier-delivery"],
        ))
    findings.sort(key=lambda finding: finding.confidence, reverse=True)
    evidence = [_evidence(result, "ev-supplier-delivery", "inventory.get_supplier_delivery_performance", f"{len(result.data)} historical received purchase-order line(s)")]
    return SkillResult(SkillStatus.OK if findings else SkillStatus.NO_DATA, findings, {"delayed_supplier_count": len(findings)}, evidence)


def _purchase_delay_stockout_risk(tool_registry, item_code=None, warehouse=None, item_group=None):
    commitments = tool_registry.get_tool("inventory.get_order_commitments")(item_code=item_code, warehouse=warehouse)
    reorder = tool_registry.get_tool("inventory.get_reorder_status")(item_code=item_code, warehouse=warehouse, item_group=item_group)
    if commitments.status != ToolStatus.OK or reorder.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=commitments.error or reorder.error)
    today = getdate(nowdate())
    reorder_by_key = {(row["item_code"], row["warehouse"]): row for row in reorder.data}
    rows = []
    for row in commitments.data:
        if row["commitment_type"] != "purchase" or not row["schedule_date"] or getdate(row["schedule_date"]) >= today:
            continue
        stock = reorder_by_key.get((row["item_code"], row["warehouse"]))
        if stock and stock["projected_qty"] < stock["rol"]:
            rows.append((row, stock))
    evidence = [
        _evidence(commitments, "ev-order-commitments", "inventory.get_order_commitments", f"Open purchase commitments checked for overdue delivery"),
        _evidence(reorder, "ev-reorder-status", "inventory.get_reorder_status", f"Reorder status checked for {len(reorder.data)} item and warehouse record(s)"),
    ]
    findings = [Finding(
        claim=(f"{row['item_code']} ({row['item_name']}) at {row['warehouse']} is at stockout risk: overdue PO {row['order_name']} from "
               f"{row['supplier']} was due on {row['schedule_date']}, while projected stock is {stock['projected_qty']:.0f} below its reorder level of {stock['rol']:.0f}."),
        confidence=0.95, supporting_evidence_ids=["ev-order-commitments", "ev-reorder-status"],
    ) for row, stock in rows]
    return SkillResult(SkillStatus.OK if findings else SkillStatus.NO_DATA, findings, {"delayed_purchase_stockout_risk_count": len(findings)}, evidence)


ORDER_PARAMS = [SkillParam("item_code", "str", required=False), SkillParam("warehouse", "str", required=False)]
OVERDUE_PURCHASE_ORDERS_SKILL = Skill("inventory.overdue_purchase_orders", "Finds open purchase orders whose scheduled delivery date has passed.", ["overdue purchase orders", "late purchase orders", "delayed incoming stock", "pending PO overdue"], ORDER_PARAMS, ["inventory.get_order_commitments"], _overdue_purchase_orders)
SUPPLIER_DELIVERY_RISK_SKILL = Skill("inventory.supplier_delivery_risk", "Finds suppliers with late historical purchase-order deliveries.", ["late suppliers", "supplier delays", "supplier lead time", "supplier delivery performance"], [SkillParam("supplier", "str", required=False), SkillParam("item_code", "str", required=False)], ["inventory.get_supplier_delivery_performance"], _supplier_delivery_risk)
PURCHASE_DELAY_STOCKOUT_RISK_SKILL = Skill("inventory.purchase_delay_stockout_risk", "Finds stockout risks where an overdue purchase order is needed to reach the reorder level.", ["stockout because purchase order delayed", "delayed PO stockout risk", "urgent delayed purchase orders"], ORDER_PARAMS + [SkillParam("item_group", "str", required=False)], ["inventory.get_order_commitments", "inventory.get_reorder_status"], _purchase_delay_stockout_risk)
