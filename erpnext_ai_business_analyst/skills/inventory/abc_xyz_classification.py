"""ABC/XYZ inventory classification from stock value and recent demand variation."""

from __future__ import annotations

from collections import defaultdict
from math import sqrt

from frappe.utils import add_months, nowdate

from erpnext_ai_business_analyst.skills.base import Evidence, Finding, Skill, SkillParam, SkillResult, SkillStatus
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


def _month_keys(months: int) -> list[str]:
    return [add_months(nowdate(), offset).strftime("%Y-%m") for offset in range(-(months - 1), 1)]


def _xyz_classification(values: list[float]) -> tuple[str, float | None]:
    mean = sum(values) / len(values)
    if mean == 0:
        return "Z", None
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    coefficient_of_variation = sqrt(variance) / mean
    if coefficient_of_variation <= 0.5:
        return "X", coefficient_of_variation
    if coefficient_of_variation <= 1.0:
        return "Y", coefficient_of_variation
    return "Z", coefficient_of_variation


def _abc_xyz_classification(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    months: int = 6,
) -> SkillResult:
    balance = tool_registry.get_tool("inventory.get_stock_balance")(
        item_code=item_code, warehouse=warehouse, item_group=item_group,
    )
    consumption = tool_registry.get_tool("inventory.get_monthly_consumption")(
        item_code=item_code, warehouse=warehouse, item_group=item_group, months=months,
    )
    if balance.status != ToolStatus.OK or consumption.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=balance.error or consumption.error)

    by_item: dict[str, dict] = {}
    for row in balance.data:
        if row["actual_qty"] <= 0:
            continue
        record = by_item.setdefault(row["item_code"], {"item_name": row["item_name"], "value": 0.0})
        record["value"] += max(row["stock_value"], 0)
    if not by_item:
        return SkillResult(status=SkillStatus.NO_DATA, metrics={"classified_item_count": 0})

    month_keys = _month_keys(months)
    outgoing: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in consumption.data:
        outgoing[row["item_code"]][row["month"]] += row["qty_out"]

    ranked = sorted(by_item.items(), key=lambda pair: pair[1]["value"], reverse=True)
    total_value = sum(record["value"] for _, record in ranked)
    cumulative_value = 0.0
    classifications = []
    for item, record in ranked:
        previous_share = cumulative_value / total_value if total_value else 0.0
        cumulative_value += record["value"]
        abc = "A" if previous_share < 0.80 else "B" if previous_share < 0.95 else "C"
        values = [outgoing[item][month] for month in month_keys]
        xyz, variation = _xyz_classification(values)
        classifications.append({
            "item_code": item, "item_name": record["item_name"], "stock_value": record["value"],
            "abc": abc, "xyz": xyz, "variation": variation, "total_issued": sum(values),
        })

    findings = []
    for row in classifications:
        demand = (
            "no recent demand" if row["variation"] is None
            else f"demand variation of {row['variation']:.2f}"
        )
        findings.append(Finding(
            claim=(f"{row['item_code']} ({row['item_name']}): {row['abc']}{row['xyz']} classification, "
                   f"stock value {row['stock_value']:.2f}; {demand} over the last {months} months."),
            confidence=0.9 if row["variation"] is not None else 0.7,
            supporting_evidence_ids=["ev-stock-balance", "ev-monthly-consumption"],
        ))
    evidence = [
        Evidence("ev-stock-balance", "inventory.get_stock_balance", vars(balance.query_meta) if balance.query_meta else {}, balance.data, f"{len(balance.data)} stock-value record(s)"),
        Evidence("ev-monthly-consumption", "inventory.get_monthly_consumption", vars(consumption.query_meta) if consumption.query_meta else {}, consumption.data, f"Monthly consumption history across {months} months"),
    ]
    return SkillResult(
        status=SkillStatus.OK, findings=findings,
        metrics={
            "classified_item_count": len(classifications),
            "a_item_count": sum(row["abc"] == "A" for row in classifications),
            "b_item_count": sum(row["abc"] == "B" for row in classifications),
            "c_item_count": sum(row["abc"] == "C" for row in classifications),
        }, evidence=evidence,
    )


SKILL = Skill(
    name="inventory.abc_xyz_classification",
    description="Classifies stock by value importance (ABC) and recent demand stability (XYZ).",
    triggers=["ABC analysis", "XYZ analysis", "inventory classification", "high value inventory", "unpredictable demand"],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("warehouse", "str", required=False),
        SkillParam("item_group", "str", required=False),
        SkillParam("months", "int", required=False, default=6),
    ],
    tools_used=["inventory.get_stock_balance", "inventory.get_monthly_consumption"],
    func=_abc_xyz_classification,
)
