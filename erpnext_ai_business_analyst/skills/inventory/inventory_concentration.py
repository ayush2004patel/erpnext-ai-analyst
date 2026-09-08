"""
Skill: inventory.inventory_concentration

Flags items whose stock is heavily concentrated in a single warehouse
(by quantity — not value, not supplier dependency; that's a V4/Purchase
concern). Aggregation across warehouses happens here in Python, using
already-fetched per-item+warehouse rows from inventory.get_item_movement
— no new SQL, no domain logic in the Tool layer.

Only items with stock in 2+ warehouses are considered; a single-warehouse
item is 100% concentrated by definition and carries no signal.

concentration_pct = (max_warehouse_stock / total_stock) * 100
Flagged when concentration_pct >= concentration_threshold_pct (default 80).
"""

from __future__ import annotations

from collections import defaultdict

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

# Confidence bands relative to the requested threshold.
CONFIDENCE_BANDS = {
    "severe": 95.0,    # concentration_pct >= 95 -> 0.9
    "flagged": 0.0,    # concentration_pct >= threshold but < severe cutoff -> 0.7
}


def _classify_confidence(concentration_pct: float) -> tuple[str, float]:
    if concentration_pct >= CONFIDENCE_BANDS["severe"]:
        return "severe", 0.9
    return "flagged", 0.7


def _inventory_concentration(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    item_group: str | None = None,
    concentration_threshold_pct: float = 80.0,
) -> SkillResult:
    movement_tool = tool_registry.get_tool("inventory.get_item_movement")
    # No warehouse filter — concentration is inherently cross-warehouse.
    result = movement_tool(item_code=item_code, item_group=item_group)

    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    if not result.data:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"concentrated_item_count": 0})

    by_item: dict[str, list[dict]] = defaultdict(list)
    for row in result.data:
        by_item[row["item_code"]].append(row)

    ev_raw_id = "ev-movement"
    ev_computed_id = "ev-concentration"

    scored: list[tuple[float, Finding]] = []
    computed_records: list[dict] = []
    evaluated_multi_warehouse_count = 0

    for item_code_key, rows in by_item.items():
        if len(rows) < 2:
            continue  # single-warehouse item — excluded per spec, no useful signal
        evaluated_multi_warehouse_count += 1

        total_stock = sum(r["stock"] for r in rows)
        if total_stock <= 0:
            continue

        max_row = max(rows, key=lambda r: r["stock"])
        max_warehouse_stock = max_row["stock"]
        concentration_pct = (max_warehouse_stock / total_stock) * 100

        if concentration_pct < concentration_threshold_pct:
            continue

        band, confidence = _classify_confidence(concentration_pct)

        claim = (
            f"{item_code_key} ({max_row['item_name']}): {concentration_pct:.1f}% of total stock "
            f"({total_stock:.0f}) sits in {max_row['warehouse']} ({max_warehouse_stock:.0f} units) "
            f"across {len(rows)} warehouses — {band} concentration."
        )

        computed_records.append({
            "item_code": item_code_key,
            "item_name": max_row["item_name"],
            "total_stock": total_stock,
            "max_warehouse": max_row["warehouse"],
            "max_warehouse_stock": max_warehouse_stock,
            "concentration_pct": concentration_pct,
            "warehouse_count": len(rows),
        })

        finding = Finding(
            claim=claim, confidence=confidence,
            supporting_evidence_ids=[ev_raw_id, ev_computed_id],
        )
        scored.append((concentration_pct, finding))

    if not scored:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"concentrated_item_count": 0})

    scored.sort(key=lambda pair: pair[0], reverse=True)
    findings = [f for _, f in scored]

    evidence = [
        Evidence(
            id=ev_raw_id, source_tool="inventory.get_item_movement",
            query_meta=vars(result.query_meta) if result.query_meta else {},
            records=result.data,
            summary=f"{len(result.data)} raw item+warehouse stock row(s)",
        ),
        Evidence(
            id=ev_computed_id, source_tool="computed:inventory_concentration",
            query_meta={}, records=computed_records,
            summary=f"{len(computed_records)} item(s) >= {concentration_threshold_pct}% concentration",
        ),
    ]

    return SkillResult(
        status=SkillStatus.OK,
        findings=findings,
        metrics={
            "concentrated_item_count": len(findings),
            "evaluated_multi_warehouse_item_count": evaluated_multi_warehouse_count,
        },
        evidence=evidence,
        suggested_next_skills=[],
    )


SKILL = Skill(
    name="inventory.inventory_concentration",
    description=(
        "Flags items whose stock (by quantity) is heavily concentrated in a "
        "single warehouse, across items held in 2+ warehouses."
    ),
    triggers=["concentration", "concentrated in one warehouse", "single location risk"],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("item_group", "str", required=False),
        SkillParam("concentration_threshold_pct", "float", required=False, default=80.0),
    ],
    tools_used=["inventory.get_item_movement"],
    func=_inventory_concentration,
)