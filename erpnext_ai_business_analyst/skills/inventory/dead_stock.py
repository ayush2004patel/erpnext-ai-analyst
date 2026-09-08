"""
Skill: inventory.dead_stock

Items with zero movement (or no movement history at all) within a
threshold window. Deterministic confidence bands based on how long the
item has been dead — never LLM-judged.

If dead-stock findings exist, suggests inventory.overstock as a next step
(V1 skill, not yet built at the time this file is written, but documents
the natural chain: dead stock is often a contributor to excess value).
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

# Configurable — multiples of the requested threshold, not absolute days,
# so raising days_threshold scales the bands with it.
CONFIDENCE_BANDS = {
    "long_dead": 2.0,   # days_since_last_movement >= threshold * 2.0 -> 0.9
    "dead": 1.0,        # days_since_last_movement >= threshold * 1.0 -> 0.7
}


def _classify_confidence(days_since_last_movement: float | None, threshold: int) -> tuple[str, float]:
    if days_since_last_movement is None:
        return "no movement history found", 0.8
    if days_since_last_movement >= threshold * CONFIDENCE_BANDS["long_dead"]:
        return "long-dead", 0.9
    return "dead", 0.7


def _dead_stock(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    days_threshold: int = 90,
) -> SkillResult:
    movement_tool = tool_registry.get_tool("inventory.get_item_movement")
    result = movement_tool(
        item_code=item_code, warehouse=warehouse, item_group=item_group,
        min_days_since_movement=days_threshold,
    )

    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    if not result.data:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"dead_item_count": 0})

    evidence_id = "ev-movement"
    evidence = Evidence(
        id=evidence_id,
        source_tool="inventory.get_item_movement",
        query_meta=vars(result.query_meta) if result.query_meta else {},
        records=result.data,
        summary=f"{len(result.data)} item+warehouse combo(s) with no movement in >= {days_threshold} days",
    )

    findings = []
    for row in result.data:
        band, confidence = _classify_confidence(row["days_since_last_movement"], days_threshold)

        if row["days_since_last_movement"] is None:
            claim = (
                f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}: "
                f"{row['stock']} in stock with no movement history found at all."
            )
        else:
            claim = (
                f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}: "
                f"{row['stock']} in stock, last moved {row['days_since_last_movement']:.0f} days ago "
                f"({band})."
            )

        findings.append(Finding(claim=claim, confidence=confidence, supporting_evidence_ids=[evidence_id]))

    suggested_next_skills = [NextSkillSuggestion(
        skill_name="inventory.overstock",
        reason="Dead stock often carries excess value relative to demand — Overstock analysis quantifies it.",
        inputs_to_pass={"warehouse": warehouse} if warehouse else {},
    )]

    return SkillResult(
        status=SkillStatus.OK,
        findings=findings,
        metrics={"dead_item_count": len(result.data)},
        evidence=[evidence],
        suggested_next_skills=suggested_next_skills,
    )


SKILL = Skill(
    name="inventory.dead_stock",
    description="Finds items with no stock movement (or no movement history) within a threshold window.",
    triggers=["dead stock", "not moved", "hasn't moved", "no movement", "stale inventory"],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("warehouse", "str", required=False),
        SkillParam("item_group", "str", required=False),
        SkillParam("days_threshold", "int", required=False, default=90),
    ],
    tools_used=["inventory.get_item_movement"],
    func=_dead_stock,
)