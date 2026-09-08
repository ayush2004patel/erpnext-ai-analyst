"""
Skill: inventory.stockout_risk

Ranks items below reorder level by estimated days-to-stockout, using
current physical stock (not projected_qty) against recent consumption rate
— deliberately conservative: pending PR/STR/PO have no guaranteed arrival
date, so we don't let unarrived supply push out the urgency estimate.
projected_qty and pending amounts are still surfaced in evidence for context.

Risk classification is a deterministic lookup against configurable
thresholds — never LLM-judged for V1, so every result is explainable and
reproducible from the same inputs.

suggested_next_skills is empty here: this Skill already has everything it
needs (reorder coverage + consumption) to explain "why". A future V2+
Lead Time or Production skill would be the natural chain target once one
exists — not invented ahead of time.
"""

from __future__ import annotations

from erpnext_ai_business_analyst.skills.base import (
    Evidence,
    Finding,
    Skill,
    SkillParam,
    SkillResult,
    SkillStatus,
)
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry

# Configurable thresholds — days_to_stockout upper bound for each level.
RISK_THRESHOLDS_DAYS = {
    "critical": 7,
    "high": 30,
    "medium": 60,
    # anything >= medium threshold -> "low"
}

CONFIDENCE_BY_RISK = {
    "critical": 0.9,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.3,
    "unclear": 0.2,  # low confidence in the *estimate*, not a risk judgment
}


def _classify_risk(days_to_stockout: float | None) -> str:
    if days_to_stockout is None:
        return "unclear"
    if days_to_stockout < RISK_THRESHOLDS_DAYS["critical"]:
        return "critical"
    if days_to_stockout < RISK_THRESHOLDS_DAYS["high"]:
        return "high"
    if days_to_stockout < RISK_THRESHOLDS_DAYS["medium"]:
        return "medium"
    return "low"


def _stockout_risk(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    window_days: int = 90,
) -> SkillResult:
    reorder_tool = tool_registry.get_tool("inventory.get_reorder_status")
    movement_tool = tool_registry.get_tool("inventory.get_item_movement")

    reorder_result = reorder_tool(
        item_code=item_code, warehouse=warehouse, item_group=item_group,
        below_rol_qty=True,
    )
    if reorder_result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=reorder_result.error)
    if not reorder_result.data:
        return SkillResult(
            status=SkillStatus.NO_DATA,
            metrics={"critical": 0, "high": 0, "medium": 0, "low": 0, "unclear": 0},
        )

    evidence: list[Evidence] = [Evidence(
        id="ev-reorder",
        source_tool="inventory.get_reorder_status",
        query_meta=vars(reorder_result.query_meta) if reorder_result.query_meta else {},
        records=reorder_result.data,
        summary=f"{len(reorder_result.data)} item+warehouse combo(s) below ROL",
    )]

    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unclear": 0}
    scored: list[tuple[float, Finding]] = []  # (sort_key, Finding) — inf for "unclear"

    for row in reorder_result.data:
        movement_result = movement_tool(
            item_code=row["item_code"], warehouse=row["warehouse"], window_days=window_days,
        )

        ev_id = f"ev-movement-{row['item_code']}-{row['warehouse']}"
        qty_out = 0.0
        if movement_result.status == ToolStatus.OK and movement_result.data:
            qty_out = movement_result.data[0]["qty_out_in_window"]
            evidence.append(Evidence(
                id=ev_id, source_tool="inventory.get_item_movement",
                query_meta=vars(movement_result.query_meta) if movement_result.query_meta else {},
                records=movement_result.data,
                summary=f"movement stats for {row['item_code']} at {row['warehouse']}",
            ))
        else:
            evidence.append(Evidence(
                id=ev_id, source_tool="inventory.get_item_movement",
                query_meta=vars(movement_result.query_meta) if movement_result.query_meta else {},
                records=[], summary="no movement data found",
            ))

        daily_consumption = (qty_out / window_days) if window_days else 0.0
        days_to_stockout = (row["stock"] / daily_consumption) if daily_consumption > 0 else None

        risk_level = _classify_risk(days_to_stockout)
        risk_counts[risk_level] += 1

        if days_to_stockout is not None:
            claim = (
                f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}: "
                f"{risk_level.upper()} stockout risk — ~{days_to_stockout:.1f} days of stock "
                f"left at current consumption ({daily_consumption:.2f}/day)."
            )
        else:
            claim = (
                f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}: below "
                f"reorder level but no consumption in the last {window_days} days — "
                f"stockout risk unclear."
            )

        finding = Finding(
            claim=claim,
            confidence=CONFIDENCE_BY_RISK[risk_level],
            supporting_evidence_ids=["ev-reorder", ev_id],
        )
        sort_key = days_to_stockout if days_to_stockout is not None else float("inf")
        scored.append((sort_key, finding))

    scored.sort(key=lambda pair: pair[0])
    findings = [f for _, f in scored]

    return SkillResult(
        status=SkillStatus.OK,
        findings=findings,
        metrics=risk_counts,
        evidence=evidence,
        suggested_next_skills=[],
    )


SKILL = Skill(
    name="inventory.stockout_risk",
    description=(
        "Ranks items below reorder level by estimated days-to-stockout, "
        "using recent consumption rate against current stock."
    ),
    triggers=[
        "at risk of stockout", "will run out", "stockout risk",
        "running low", "out of stock soon",
    ],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("warehouse", "str", required=False),
        SkillParam("item_group", "str", required=False),
        SkillParam("window_days", "int", required=False, default=90),
    ],
    tools_used=["inventory.get_reorder_status", "inventory.get_item_movement"],
    func=_stockout_risk,
)