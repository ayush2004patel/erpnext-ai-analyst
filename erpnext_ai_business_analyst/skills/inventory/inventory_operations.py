"""Operational inventory skills for orders, expiry, configuration, and movement reporting."""

from __future__ import annotations

from erpnext_ai_business_analyst.skills.base import Evidence, Finding, Skill, SkillParam, SkillResult, SkillStatus
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


def _evidence(result, evidence_id, tool_name, summary):
    return Evidence(evidence_id, tool_name, vars(result.query_meta) if result.query_meta else {}, result.data, summary)


def _open_purchase_orders(tool_registry, item_code=None, warehouse=None):
    result = tool_registry.get_tool("inventory.get_order_commitments")(item_code=item_code, warehouse=warehouse)
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    rows = [r for r in result.data if r["commitment_type"] == "purchase"]
    evidence = _evidence(result, "ev-order-commitments", "inventory.get_order_commitments", f"{len(rows)} open purchase-order line(s)")
    findings = [Finding(f"Purchase order {r['order_name']} will supply {r['open_qty']:.0f} of {r['item_code']} ({r['item_name']}) to {r['warehouse']} by {r['schedule_date']}.", 0.95, [evidence.id]) for r in rows]
    return SkillResult(SkillStatus.OK if findings else SkillStatus.NO_DATA, findings, {"open_purchase_order_line_count": len(findings)}, [evidence])


def _sales_commitments(tool_registry, item_code=None, warehouse=None):
    result = tool_registry.get_tool("inventory.get_order_commitments")(item_code=item_code, warehouse=warehouse)
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    rows = [r for r in result.data if r["commitment_type"] == "sales"]
    evidence = _evidence(result, "ev-order-commitments", "inventory.get_order_commitments", f"{len(rows)} outstanding sales-order line(s)")
    findings = [Finding(f"Sales order {r['order_name']} still requires {r['open_qty']:.0f} of {r['item_code']} ({r['item_name']}) from {r['warehouse']} by {r['schedule_date']}.", 0.95, [evidence.id]) for r in rows]
    return SkillResult(SkillStatus.OK if findings else SkillStatus.NO_DATA, findings, {"outstanding_sales_order_line_count": len(findings)}, [evidence])


def _expiring_batches(tool_registry, item_code=None, days_ahead=90):
    result = tool_registry.get_tool("inventory.get_batch_expiry")(item_code=item_code, days_ahead=days_ahead)
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    evidence = _evidence(result, "ev-batch-expiry", "inventory.get_batch_expiry", f"{len(result.data)} batch(es) expiring within {days_ahead} days")
    findings = []
    for r in result.data:
        timing = "has already expired" if r["days_to_expiry"] < 0 else f"expires in {r['days_to_expiry']} days"
        findings.append(Finding(f"Batch {r['batch']} for {r['item_code']} ({r['item_name']}) {timing}, on {r['expiry_date']}.", 0.95, [evidence.id]))
    return SkillResult(SkillStatus.OK if findings else SkillStatus.NO_DATA, findings, {"expiring_batch_count": len(findings)}, [evidence])


def _reorder_configuration_gap(tool_registry, item_code=None, warehouse=None, item_group=None):
    balance = tool_registry.get_tool("inventory.get_stock_balance")(item_code=item_code, warehouse=warehouse, item_group=item_group)
    reorder = tool_registry.get_tool("inventory.get_reorder_status")(item_code=item_code, warehouse=warehouse, item_group=item_group)
    if balance.status != ToolStatus.OK or reorder.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=balance.error or reorder.error)
    configured = {(r["item_code"], r["warehouse"]) for r in reorder.data}
    rows = [r for r in balance.data if r["actual_qty"] > 0 and (r["item_code"], r["warehouse"]) not in configured]
    evidence = _evidence(balance, "ev-stock-balance", "inventory.get_stock_balance", f"{len(balance.data)} stocked item and warehouse record(s)")
    findings = [Finding(f"{r['item_code']} ({r['item_name']}) at {r['warehouse']} has {r['actual_qty']:.0f} {r['uom']} in stock but no reorder level is configured.", 0.9, [evidence.id]) for r in rows]
    return SkillResult(SkillStatus.OK if findings else SkillStatus.NO_DATA, findings, {"missing_reorder_configuration_count": len(findings)}, [evidence])


def _movement_summary(tool_registry, item_code=None, warehouse=None, item_group=None, window_days=90):
    result = tool_registry.get_tool("inventory.get_item_movement")(item_code=item_code, warehouse=warehouse, item_group=item_group, window_days=window_days)
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    evidence = _evidence(result, "ev-item-movement", "inventory.get_item_movement", f"Movement summary for {len(result.data)} item and warehouse record(s) over {window_days} days")
    findings = [Finding(f"{r['item_code']} ({r['item_name']}) at {r['warehouse']}: {r['qty_in_in_window']:.0f} received and {r['qty_out_in_window']:.0f} issued in the last {window_days} days ({r['movement_count_in_window']:.0f} movements).", 1.0, [evidence.id]) for r in result.data]
    return SkillResult(SkillStatus.OK if findings else SkillStatus.NO_DATA, findings, {"movement_summary_record_count": len(findings)}, [evidence])


ORDER_PARAMS = [SkillParam("item_code", "str", required=False), SkillParam("warehouse", "str", required=False)]
FILTER_PARAMS = ORDER_PARAMS + [SkillParam("item_group", "str", required=False)]
OPEN_PURCHASE_ORDERS_SKILL = Skill("inventory.open_purchase_orders", "Shows open purchase orders that will supply inventory.", ["open purchase orders", "incoming stock", "pending purchase order", "when will stock arrive"], ORDER_PARAMS, ["inventory.get_order_commitments"], _open_purchase_orders)
SALES_COMMITMENTS_SKILL = Skill("inventory.sales_commitments", "Shows outstanding sales orders that consume inventory.", ["sales order commitments", "reserved for sales", "outstanding sales orders", "customer demand"], ORDER_PARAMS, ["inventory.get_order_commitments"], _sales_commitments)
EXPIRING_BATCHES_SKILL = Skill("inventory.expiring_batches", "Finds batches that are expired or due to expire soon.", ["expiring stock", "expired batches", "near expiry", "batch expiry"], [SkillParam("item_code", "str", required=False), SkillParam("days_ahead", "int", required=False, default=90)], ["inventory.get_batch_expiry"], _expiring_batches)
REORDER_GAP_SKILL = Skill("inventory.reorder_configuration_gap", "Finds stocked items that have no reorder level configured.", ["missing reorder level", "items without reorder configuration", "reorder settings gap"], FILTER_PARAMS, ["inventory.get_stock_balance", "inventory.get_reorder_status"], _reorder_configuration_gap)
MOVEMENT_SUMMARY_SKILL = Skill("inventory.stock_movement_summary", "Shows incoming and outgoing stock movement in a selected period.", ["stock movement report", "inventory movement", "stock received and issued", "movement summary"], FILTER_PARAMS + [SkillParam("window_days", "int", required=False, default=90)], ["inventory.get_item_movement"], _movement_summary)
