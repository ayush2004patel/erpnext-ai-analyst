"""
Skill: inventory.overstock

Flags items whose current stock is excessive relative to their reorder
position — stock >= overstock_multiplier x ROL. Separate concern from
inventory_concentration (which only asks about single-warehouse risk):
this asks whether the item is over-supplied relative to its own
demand/reorder baseline, regardless of how it's spread across warehouses.

Confidence is driven by the stock/ROL ratio alone — deterministic bands,
same pattern as the other V1 skills. Consumption data (coverage_days) is
pulled in as supporting context in the claim text, not as a second
threshold — keeps the rule single-signal and easy to explain.
"""

from __future__ import annotations

from erpnext_ai_business_analyst.skills.base import (
    Evidence,
    Finding,
    NextSkillSuggestion,
    Skill,
    SkillParam,
    SkillResult,
    SkillStatus,
)
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry

# Confidence bands relative to the requested multiplier.
CONFIDENCE_BANDS = {
    "severe": 2.0,     # ratio >= multiplier * 2.0 -> 0.9
}


def _classify_confidence(ratio: float, multiplier: float) -> tuple[str, float]:
    if ratio >= multiplier * CONFIDENCE_BANDS["severe"]:
        return "severe", 0.9
    return "flagged", 0.7


def _overstock(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    overstock_multiplier: float = 3.0,
    window_days: int = 90,
) -> SkillResult:
    reorder_tool = tool_registry.get_tool("inventory.get_reorder_status")
    movement_tool = tool_registry.get_tool("inventory.get_item_movement")

    # No trigger/below-ROL filter here — overstock is the opposite case.
    reorder_result = reorder_tool(item_code=item_code, warehouse=warehouse, item_group=item_group)

    if reorder_result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=reorder_result.error)
    if not reorder_result.data:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"overstocked_item_count": 0})

    flagged_rows = [
        row for row in reorder_result.data
        if row["rol"] and row["rol"] > 0 and row["stock"] >= overstock_multiplier * row["rol"]
    ]

    if not flagged_rows:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"overstocked_item_count": 0})

    evidence: list[Evidence] = [Evidence(
        id="ev-reorder", source_tool="inventory.get_reorder_status",
        query_meta=vars(reorder_result.query_meta) if reorder_result.query_meta else {},
        records=flagged_rows,
        summary=f"{len(flagged_rows)} item+warehouse combo(s) with stock >= {overstock_multiplier}x ROL",
    )]

    scored: list[tuple[float, Finding]] = []

    for row in flagged_rows:
        ratio = row["stock"] / row["rol"]
        band, confidence = _classify_confidence(ratio, overstock_multiplier)

        movement_result = movement_tool(
            item_code=row["item_code"], warehouse=row["warehouse"], window_days=window_days,
        )
        ev_id = f"ev-movement-{row['item_code']}-{row['warehouse']}"
        coverage_note = ""
        if movement_result.status == ToolStatus.OK and movement_result.data:
            qty_out = movement_result.data[0]["qty_out_in_window"]
            evidence.append(Evidence(
                id=ev_id, source_tool="inventory.get_item_movement",
                query_meta=vars(movement_result.query_meta) if movement_result.query_meta else {},
                records=movement_result.data,
                summary=f"movement stats for {row['item_code']} at {row['warehouse']}",
            ))
            if qty_out and qty_out > 0:
                daily_consumption = qty_out / window_days
                coverage_days = row["stock"] / daily_consumption
                coverage_note = f" (~{coverage_days:.0f} days of coverage at current pace)"
            else:
                coverage_note = " (no recent consumption)"
        else:
            evidence.append(Evidence(
                id=ev_id, source_tool="inventory.get_item_movement",
                query_meta=vars(movement_result.query_meta) if movement_result.query_meta else {},
                records=[], summary="no movement data found",
            ))

        claim = (
            f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}: stock {row['stock']:.0f} "
            f"is {ratio:.1f}x its ROL ({row['rol']:.0f}) — {band} overstock.{coverage_note}"
        )

        finding = Finding(
            claim=claim, confidence=confidence,
            supporting_evidence_ids=["ev-reorder", ev_id],
        )
        scored.append((ratio, finding))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    findings = [f for _, f in scored]

    return SkillResult(
        status=SkillStatus.OK,
        findings=findings,
        metrics={"overstocked_item_count": len(flagged_rows)},
        evidence=evidence,
        suggested_next_skills=[NextSkillSuggestion(
            skill_name="inventory.slow_moving_stock",
            reason="Overstocked items are often also slow-moving — cross-check consumption pace.",
            inputs_to_pass={"warehouse": warehouse} if warehouse else {},
        )],
    )


SKILL = Skill(
    name="inventory.overstock",
    description=(
        "Flags items whose current stock is excessive relative to their "
        "reorder position (stock >= multiplier x ROL)."
    ),
    triggers=["stock is too high", "why is stock high", "overstock", "excess stock"],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("warehouse", "str", required=False),
        SkillParam("item_group", "str", required=False),
        SkillParam("overstock_multiplier", "float", required=False, default=3.0),
        SkillParam("window_days", "int", required=False, default=90),
    ],
    tools_used=["inventory.get_reorder_status", "inventory.get_item_movement"],
    func=_overstock,
)