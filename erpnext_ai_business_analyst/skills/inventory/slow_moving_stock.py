"""
Skill: inventory.slow_moving_stock

Items that HAVE moved recently (unlike Dead Stock) but at a rate too low
relative to current stock — i.e. current stock would take an excessive
number of days to sell through at the recent consumption pace.

coverage_days = stock / (qty_out_in_window / window_days)

Only considers items with qty_out_in_window > 0 — zero-movement items are
Dead Stock's territory, not this Skill's. Deterministic confidence bands
against a configurable coverage-days threshold — never LLM-judged.
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

# Configurable — coverage_days multiples of the requested threshold.
CONFIDENCE_BANDS = {
    "severe": 2.0,     # coverage_days >= threshold * 2.0 -> 0.9
    "moderate": 1.0,   # coverage_days >= threshold * 1.0 -> 0.6
}


def _classify_confidence(coverage_days: float, threshold: int) -> tuple[str, float]:
    if coverage_days >= threshold * CONFIDENCE_BANDS["severe"]:
        return "severe", 0.9
    return "moderate", 0.6


def _slow_moving_stock(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    window_days: int = 90,
    coverage_days_threshold: int = 180,
) -> SkillResult:
    movement_tool = tool_registry.get_tool("inventory.get_item_movement")
    result = movement_tool(
        item_code=item_code, warehouse=warehouse, item_group=item_group,
        window_days=window_days,
    )

    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    if not result.data:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"slow_moving_item_count": 0})

    evidence_id = "ev-movement"
    matched_rows = []
    findings: list[Finding] = []

    for row in result.data:
        qty_out = row["qty_out_in_window"]
        if not qty_out or qty_out <= 0:
            continue  # no recent movement at all -> Dead Stock's territory, skip here

        daily_consumption = qty_out / window_days
        coverage_days = row["stock"] / daily_consumption if daily_consumption > 0 else None
        if coverage_days is None or coverage_days < coverage_days_threshold:
            continue  # moving fast enough, not slow

        band, confidence = _classify_confidence(coverage_days, coverage_days_threshold)
        matched_rows.append(row)

        claim = (
            f"{row['item_code']} ({row['item_name']}) at {row['warehouse']}: "
            f"{row['stock']} in stock would take ~{coverage_days:.0f} days to sell through "
            f"at the current pace ({daily_consumption:.2f}/day) — {band} slow-moving."
        )
        findings.append(Finding(claim=claim, confidence=confidence, supporting_evidence_ids=[evidence_id]))

    if not findings:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"slow_moving_item_count": 0})

    findings.sort(key=lambda f: f.confidence, reverse=True)

    evidence = Evidence(
        id=evidence_id,
        source_tool="inventory.get_item_movement",
        query_meta=vars(result.query_meta) if result.query_meta else {},
        records=matched_rows,
        summary=f"{len(matched_rows)} item+warehouse combo(s) moving but coverage >= {coverage_days_threshold} days",
    )

    return SkillResult(
        status=SkillStatus.OK,
        findings=findings,
        metrics={"slow_moving_item_count": len(matched_rows)},
        evidence=[evidence],
        suggested_next_skills=[],
    )


SKILL = Skill(
    name="inventory.slow_moving_stock",
    description=(
        "Finds items that have moved recently but at a rate too low relative "
        "to current stock — long coverage-days at current consumption pace."
    ),
    triggers=["slow moving", "low turnover", "moving slowly", "excess coverage"],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("warehouse", "str", required=False),
        SkillParam("item_group", "str", required=False),
        SkillParam("window_days", "int", required=False, default=90),
        SkillParam("coverage_days_threshold", "int", required=False, default=180),
    ],
    tools_used=["inventory.get_item_movement"],
    func=_slow_moving_stock,
)