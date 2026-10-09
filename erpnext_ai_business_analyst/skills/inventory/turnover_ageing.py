"""Inventory ageing value and turnover analysis from current stock and movement history."""

from __future__ import annotations

from erpnext_ai_business_analyst.skills.base import Evidence, Finding, Skill, SkillParam, SkillResult, SkillStatus
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


def _evidence(result, evidence_id, tool_name, summary):
    return Evidence(evidence_id, tool_name, vars(result.query_meta) if result.query_meta else {}, result.data, summary)


def _ageing_value(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    min_age_days: int = 90,
) -> SkillResult:
    balance = tool_registry.get_tool("inventory.get_stock_balance")(item_code=item_code, warehouse=warehouse, item_group=item_group)
    movement = tool_registry.get_tool("inventory.get_item_movement")(
        item_code=item_code, warehouse=warehouse, item_group=item_group, min_days_since_movement=min_age_days,
    )
    if balance.status != ToolStatus.OK or movement.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=balance.error or movement.error)
    balance_by_key = {(row["item_code"], row["warehouse"]): row for row in balance.data}
    rows = []
    for movement_row in movement.data:
        balance_row = balance_by_key.get((movement_row["item_code"], movement_row["warehouse"]))
        if balance_row and balance_row["actual_qty"] > 0:
            rows.append({**movement_row, "stock_value": balance_row["stock_value"]})
    rows.sort(key=lambda row: row["stock_value"], reverse=True)
    evidence = [
        _evidence(balance, "ev-stock-balance", "inventory.get_stock_balance", f"{len(balance.data)} current stock-value record(s)"),
        _evidence(movement, "ev-item-movement", "inventory.get_item_movement", f"{len(movement.data)} item and warehouse record(s) inactive for at least {min_age_days} days"),
    ]
    findings = []
    for row in rows:
        age = "no movement history" if row["days_since_last_movement"] is None else f"{row['days_since_last_movement']:.0f} days without movement"
        findings.append(Finding(
            claim=(f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}: ageing stock value "
                   f"{row['stock_value']:.2f} for {row['stock']:.0f} {row['uom']} — {age}."),
            confidence=0.95 if row["days_since_last_movement"] is None or row["days_since_last_movement"] >= min_age_days * 2 else 0.8,
            supporting_evidence_ids=["ev-stock-balance", "ev-item-movement"],
        ))
    return SkillResult(
        status=SkillStatus.OK if findings else SkillStatus.NO_DATA, findings=findings,
        metrics={"ageing_stock_count": len(findings), "ageing_stock_value": sum(row["stock_value"] for row in rows)}, evidence=evidence,
    )


def _inventory_turnover(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    window_days: int = 90,
    low_turnover_threshold: float = 0.5,
) -> SkillResult:
    movement = tool_registry.get_tool("inventory.get_item_movement")(
        item_code=item_code, warehouse=warehouse, item_group=item_group, window_days=window_days,
    )
    if movement.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=movement.error)
    rows = []
    for row in movement.data:
        if row["stock"] <= 0 or row["qty_out_in_window"] <= 0:
            continue
        # Approximate average inventory using current stock plus half of the issued quantity.
        average_inventory = row["stock"] + (row["qty_out_in_window"] / 2)
        turnover = row["qty_out_in_window"] / average_inventory
        if turnover <= low_turnover_threshold:
            rows.append((turnover, row))
    rows.sort(key=lambda pair: pair[0])
    evidence = [_evidence(movement, "ev-item-movement", "inventory.get_item_movement", f"Movement data for {len(movement.data)} item and warehouse record(s) over {window_days} days")]
    findings = [Finding(
        claim=(f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}: low turnover of {turnover:.2f} "
               f"over {window_days} days ({row['qty_out_in_window']:.0f} {row['uom']} issued; {row['stock']:.0f} currently in stock)."),
        confidence=0.9 if turnover <= low_turnover_threshold / 2 else 0.75,
        supporting_evidence_ids=["ev-item-movement"],
    ) for turnover, row in rows]
    return SkillResult(
        status=SkillStatus.OK if findings else SkillStatus.NO_DATA, findings=findings,
        metrics={"low_turnover_item_count": len(findings)}, evidence=evidence,
    )


FILTER_PARAMS = [
    SkillParam("item_code", "str", required=False),
    SkillParam("warehouse", "str", required=False),
    SkillParam("item_group", "str", required=False),
]
AGEING_VALUE_SKILL = Skill(
    name="inventory.ageing_value",
    description="Shows the financial value of stock that has not moved for a selected period.",
    triggers=["ageing inventory value", "value of dead stock", "old stock value", "money tied up in inventory"],
    params=FILTER_PARAMS + [SkillParam("min_age_days", "int", required=False, default=90)],
    tools_used=["inventory.get_stock_balance", "inventory.get_item_movement"], func=_ageing_value,
)
TURNOVER_SKILL = Skill(
    name="inventory.inventory_turnover",
    description="Finds items with low recent inventory turnover based on issued quantity and current stock.",
    triggers=["inventory turnover", "low turnover items", "slow turnover", "items held too long"],
    params=FILTER_PARAMS + [SkillParam("window_days", "int", required=False, default=90), SkillParam("low_turnover_threshold", "float", required=False, default=0.5)],
    tools_used=["inventory.get_item_movement"], func=_inventory_turnover,
)
