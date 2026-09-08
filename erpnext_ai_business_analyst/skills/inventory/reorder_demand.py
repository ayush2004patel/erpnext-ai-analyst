"""
Skill: inventory.reorder_demand

Wraps inventory.get_reorder_status into structured findings: items below
reorder level with insufficient pending coverage, ranked by confidence.

Confidence rule (deliberately simple/rule-based for V1 — not LLM-judged):
  - trigger_qty > 0 AND pending_pr == pending_str == pending_po == 0
      -> 0.9  (below ROL, nothing at all inbound)
  - trigger_qty > 0 AND some pending exists but still short
      -> 0.6  (already ordering, may resolve on its own — lower confidence
               this is an actionable gap)
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


def _reorder_demand(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
) -> SkillResult:
    tool = tool_registry.get_tool("inventory.get_reorder_status")
    result = tool(
        item_code=item_code,
        warehouse=warehouse,
        item_group=item_group,
        trigger_qty_only=True,
    )

    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)

    if not result.data:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"triggered_item_count": 0})

    evidence_id = "ev-1"
    evidence = Evidence(
        id=evidence_id,
        source_tool="inventory.get_reorder_status",
        query_meta=vars(result.query_meta) if result.query_meta else {},
        records=result.data,
        summary=f"{len(result.data)} item+warehouse combo(s) below trigger threshold",
    )

    findings = []
    total_trigger_qty = 0.0
    for row in result.data:
        has_any_pending = bool(row["pending_pr"] or row["pending_str"] or row["pending_po"])
        confidence = 0.6 if has_any_pending else 0.9

        claim = (
            f"{row['item_code']} ({row['item_name']}) at {row['warehouse']} is below "
            f"reorder level — projected qty {row['projected_qty']} vs ROL {row['rol']}, "
            f"trigger qty {row['trigger_qty']}"
        )
        if not has_any_pending:
            claim += " — no pending PR, STR, or PO covering it."

        findings.append(Finding(
            claim=claim,
            confidence=confidence,
            supporting_evidence_ids=[evidence_id],
        ))
        total_trigger_qty += row["trigger_qty"]

    return SkillResult(
        status=SkillStatus.OK,
        findings=findings,
        metrics={
            "triggered_item_count": len(result.data),
            "total_trigger_qty": total_trigger_qty,
        },
        evidence=[evidence],
        suggested_next_skills=[],  # inventory.stockout_risk not built yet
    )


SKILL = Skill(
    name="inventory.reorder_demand",
    description=(
        "Finds items below reorder level with insufficient pending "
        "PR/STR/PO coverage — reorder/demand risk."
    ),
    triggers=[
        "reorder", "below reorder level", "no pending po",
        "need to restock", "reorder level", "demand analysis",
    ],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("warehouse", "str", required=False),
        SkillParam("item_group", "str", required=False),
    ],
    tools_used=["inventory.get_reorder_status"],
    func=_reorder_demand,
)