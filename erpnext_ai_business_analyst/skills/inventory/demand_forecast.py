"""Demand forecast versus actual consumption using completed monthly history."""

from __future__ import annotations

from collections import defaultdict

from frappe.utils import add_months, getdate, nowdate

from erpnext_ai_business_analyst.skills.base import Evidence, Finding, Skill, SkillParam, SkillResult, SkillStatus
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


def _month_key(offset: int) -> str:
    return getdate(add_months(nowdate(), offset)).strftime("%Y-%m")


def _demand_forecast_vs_actual(
    tool_registry: ToolRegistry,
    item_code: str | None = None,
    warehouse: str | None = None,
    item_group: str | None = None,
    lookback_months: int = 3,
    variance_threshold_pct: float = 20.0,
) -> SkillResult:
    # Ask for one extra partial month so the required completed months are all present.
    result = tool_registry.get_tool("inventory.get_monthly_consumption")(
        item_code=item_code, warehouse=warehouse, item_group=item_group, months=lookback_months + 2,
    )
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)

    actual_month = _month_key(-1)
    history_months = [_month_key(offset) for offset in range(-(lookback_months + 1), -1)]
    by_item: dict[str, dict] = {}
    for row in result.data:
        record = by_item.setdefault(row["item_code"], {"item_name": row["item_name"], "months": defaultdict(float)})
        record["months"][row["month"]] += row["qty_out"]

    records = []
    for code, record in by_item.items():
        history = [record["months"][month] for month in history_months]
        forecast = sum(history) / lookback_months
        if forecast <= 0:
            continue
        actual = record["months"][actual_month]
        variance_pct = ((actual - forecast) / forecast) * 100
        if abs(variance_pct) >= variance_threshold_pct:
            records.append({
                "item_code": code, "item_name": record["item_name"], "forecast": forecast,
                "actual": actual, "variance_pct": variance_pct,
            })
    records.sort(key=lambda row: abs(row["variance_pct"]), reverse=True)
    evidence = Evidence(
        "ev-monthly-consumption", "inventory.get_monthly_consumption",
        vars(result.query_meta) if result.query_meta else {}, result.data,
        f"Monthly consumption used to compare {actual_month} with the preceding {lookback_months} completed months",
    )
    findings = []
    for row in records:
        direction = "above" if row["variance_pct"] > 0 else "below"
        findings.append(Finding(
            claim=(f"{row['item_code']} ({row['item_name']}): {actual_month} consumption was {row['actual']:.0f} units, "
                   f"{abs(row['variance_pct']):.0f}% {direction} the forecast of {row['forecast']:.0f} units. "
                   f"Expected demand for the next month is about {row['forecast']:.0f} units."),
            confidence=0.8, supporting_evidence_ids=[evidence.id],
        ))
    return SkillResult(
        status=SkillStatus.OK if findings else SkillStatus.NO_DATA, findings=findings,
        metrics={"forecast_variance_item_count": len(findings), "actual_month": actual_month}, evidence=[evidence],
    )


SKILL = Skill(
    name="inventory.demand_forecast_vs_actual",
    description="Compares a moving-average demand forecast with the latest completed month's actual consumption.",
    triggers=["demand forecast", "forecast versus actual", "consumption above forecast", "expected demand next month", "forecast accuracy"],
    params=[
        SkillParam("item_code", "str", required=False),
        SkillParam("warehouse", "str", required=False),
        SkillParam("item_group", "str", required=False),
        SkillParam("lookback_months", "int", required=False, default=3),
        SkillParam("variance_threshold_pct", "float", required=False, default=20.0),
    ],
    tools_used=["inventory.get_monthly_consumption"], func=_demand_forecast_vs_actual,
)
