"""Checks common inventory master-data and balance-quality problems."""

from __future__ import annotations

from erpnext_ai_business_analyst.skills.base import Evidence, Finding, Skill, SkillParam, SkillResult, SkillStatus
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


def _inventory_data_quality_audit(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
) -> SkillResult:
    balance = tool_registry.get_tool("inventory.get_stock_balance")(item_code=item_code, warehouse=warehouse, item_group=item_group)
    reorder = tool_registry.get_tool("inventory.get_reorder_status")(item_code=item_code, warehouse=warehouse, item_group=item_group)
    if balance.status != ToolStatus.OK or reorder.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=balance.error or reorder.error)

    configured_reorder = {(row["item_code"], row["warehouse"]) for row in reorder.data}
    findings = []
    for row in balance.data:
        evidence_ids = ["ev-stock-balance"]
        item_label = f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}"
        if row["actual_qty"] < 0:
            findings.append(Finding(f"{item_label} has negative stock of {row['actual_qty']:.0f} {row['uom']}; investigate stock entries and reconcile the balance.", 0.95, evidence_ids))
        if row["actual_qty"] > 0 and (row["stock_value"] <= 0 or row["valuation_rate"] <= 0):
            findings.append(Finding(f"{item_label} has {row['actual_qty']:.0f} {row['uom']} in stock but zero or missing valuation; review the valuation rate and stock entries.", 0.9, evidence_ids))
        if row["reserved_qty"] > row["actual_qty"]:
            findings.append(Finding(f"{item_label} has {row['reserved_qty']:.0f} {row['uom']} reserved against only {row['actual_qty']:.0f} in stock; review reservations and fulfilment commitments.", 0.9, evidence_ids))
        if row["actual_qty"] > 0 and (row["item_code"], row["warehouse"]) not in configured_reorder:
            findings.append(Finding(f"{item_label} has stock but no reorder level configured; add a reorder setting if this item needs replenishment control.", 0.8, evidence_ids))

    evidence = [
        Evidence("ev-stock-balance", "inventory.get_stock_balance", vars(balance.query_meta) if balance.query_meta else {}, balance.data, f"{len(balance.data)} stock balance record(s) checked"),
        Evidence("ev-reorder-status", "inventory.get_reorder_status", vars(reorder.query_meta) if reorder.query_meta else {}, reorder.data, f"{len(reorder.data)} reorder configuration record(s) checked"),
    ]
    return SkillResult(
        status=SkillStatus.OK if findings else SkillStatus.NO_DATA, findings=findings,
        metrics={"inventory_data_quality_issue_count": len(findings)}, evidence=evidence,
    )


SKILL = Skill(
    name="inventory.data_quality_audit",
    description="Checks stock balances and replenishment setup for common inventory data-quality issues.",
    triggers=["inventory data quality", "inventory audit", "stock data problems", "zero valuation stock", "inventory setup issues"],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("warehouse", "str", required=False),
        SkillParam("item_group", "str", required=False),
    ],
    tools_used=["inventory.get_stock_balance", "inventory.get_reorder_status"],
    func=_inventory_data_quality_audit,
)
