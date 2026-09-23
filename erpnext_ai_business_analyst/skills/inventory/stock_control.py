"""Core stock-control skills built on standard ERPNext Bin and SLE data."""

from __future__ import annotations

from collections import defaultdict

from erpnext_ai_business_analyst.skills.base import Evidence, Finding, Skill, SkillParam, SkillResult, SkillStatus
from erpnext_ai_business_analyst.tools.base import ToolStatus
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


FILTER_PARAMS = [
    SkillParam("item_code", "str", required=False),
    SkillParam("warehouse", "str", required=False),
    SkillParam("item_group", "str", required=False),
]


def _balance(tool_registry: ToolRegistry, **kwargs):
    result = tool_registry.get_tool("inventory.get_stock_balance")(**kwargs)
    if result.status != ToolStatus.OK:
        return None, None
    evidence = Evidence(
        id="ev-stock-balance", source_tool="inventory.get_stock_balance",
        query_meta=vars(result.query_meta) if result.query_meta else {}, records=result.data,
        summary=f"{len(result.data)} item and warehouse stock record(s)",
    )
    return result, evidence


def _result(findings, evidence, metrics):
    return SkillResult(
        status=SkillStatus.OK if findings else SkillStatus.NO_DATA,
        findings=findings, evidence=[evidence] if evidence else [], metrics=metrics,
    )


def _stock_balance(tool_registry: ToolRegistry, **kwargs) -> SkillResult:
    result, evidence = _balance(tool_registry, **kwargs)
    if result is None:
        return SkillResult(status=SkillStatus.ERROR, error="Unable to read stock balance")
    findings = [Finding(
        claim=(f"{r['item_code']} ({r['item_name']}) at {r['warehouse']}: {r['actual_qty']:.0f} {r['uom']} in stock, "
               f"{r['reserved_qty']:.0f} reserved, {r['projected_qty']:.0f} projected."),
        confidence=1.0, supporting_evidence_ids=[evidence.id],
    ) for r in result.data]
    return _result(findings, evidence, {"stock_record_count": len(findings)})


def _available_stock(tool_registry: ToolRegistry, **kwargs) -> SkillResult:
    result, evidence = _balance(tool_registry, **kwargs)
    if result is None:
        return SkillResult(status=SkillStatus.ERROR, error="Unable to read stock balance")
    findings = []
    for r in result.data:
        available = r["actual_qty"] - r["reserved_qty"]
        findings.append(Finding(
            claim=(f"{r['item_code']} ({r['item_name']}) at {r['warehouse']}: {available:.0f} {r['uom']} available "
                   f"after reserving {r['reserved_qty']:.0f} of {r['actual_qty']:.0f} in stock."),
            confidence=1.0, supporting_evidence_ids=[evidence.id],
        ))
    findings.sort(key=lambda f: float(f.claim.split(": ")[1].split()[0]))
    return _result(findings, evidence, {"available_stock_record_count": len(findings)})


def _negative_stock(tool_registry: ToolRegistry, **kwargs) -> SkillResult:
    result, evidence = _balance(tool_registry, **kwargs)
    if result is None:
        return SkillResult(status=SkillStatus.ERROR, error="Unable to read stock balance")
    rows = [r for r in result.data if r["actual_qty"] < 0]
    findings = [Finding(
        claim=f"{r['item_code']} ({r['item_name']}) at {r['warehouse']} has negative stock of {r['actual_qty']:.0f} {r['uom']}.",
        confidence=0.95, supporting_evidence_ids=[evidence.id],
    ) for r in rows]
    return _result(findings, evidence, {"negative_stock_count": len(findings)})


def _inventory_valuation(tool_registry: ToolRegistry, **kwargs) -> SkillResult:
    result, evidence = _balance(tool_registry, **kwargs)
    if result is None:
        return SkillResult(status=SkillStatus.ERROR, error="Unable to read stock balance")
    rows = sorted(result.data, key=lambda r: r["stock_value"], reverse=True)
    findings = [Finding(
        claim=(f"{r['item_code']} ({r['item_name']}) at {r['warehouse']}: stock value {r['stock_value']:.2f} "
               f"for {r['actual_qty']:.0f} {r['uom']} at a valuation rate of {r['valuation_rate']:.2f}."),
        confidence=1.0, supporting_evidence_ids=[evidence.id],
    ) for r in rows]
    return _result(findings, evidence, {"valued_stock_record_count": len(findings), "total_stock_value": sum(r["stock_value"] for r in rows)})


def _warehouse_imbalance(tool_registry: ToolRegistry, item_code=None, item_group=None, concentration_threshold_pct: float = 80.0) -> SkillResult:
    result, evidence = _balance(tool_registry, item_code=item_code, warehouse=None, item_group=item_group)
    if result is None:
        return SkillResult(status=SkillStatus.ERROR, error="Unable to read stock balance")
    by_item = defaultdict(list)
    for row in result.data:
        if row["actual_qty"] > 0:
            by_item[row["item_code"]].append(row)
    findings = []
    for rows in by_item.values():
        if len(rows) < 2:
            continue
        total = sum(r["actual_qty"] for r in rows)
        largest = max(rows, key=lambda r: r["actual_qty"])
        share = largest["actual_qty"] * 100 / total
        if share >= concentration_threshold_pct:
            findings.append(Finding(
                claim=(f"{largest['item_code']} ({largest['item_name']}): {share:.0f}% of {total:.0f} {largest['uom']} is in "
                       f"{largest['warehouse']}; review whether stock should be transferred to other warehouses."),
                confidence=0.9 if share >= 95 else 0.75, supporting_evidence_ids=[evidence.id],
            ))
    return _result(findings, evidence, {"warehouse_imbalance_count": len(findings)})


def _stock_coverage(tool_registry: ToolRegistry, item_code=None, warehouse=None, item_group=None, window_days: int = 90) -> SkillResult:
    result = tool_registry.get_tool("inventory.get_item_movement")(item_code=item_code, warehouse=warehouse, item_group=item_group, window_days=window_days)
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    evidence = Evidence("ev-item-movement", "inventory.get_item_movement", vars(result.query_meta) if result.query_meta else {}, result.data, f"{len(result.data)} stock movement record(s) over {window_days} days")
    findings = []
    for r in result.data:
        if r["qty_out_in_window"] <= 0 or r["stock"] <= 0:
            continue
        coverage = r["stock"] / (r["qty_out_in_window"] / window_days)
        findings.append(Finding(
            claim=(f"{r['item_code']} ({r['item_name']}) at {r['warehouse']}: current stock of {r['stock']:.0f} {r['uom']} "
                   f"covers about {coverage:.0f} days at the recent consumption rate."),
            confidence=0.8, supporting_evidence_ids=[evidence.id],
        ))
    findings.sort(key=lambda f: float(f.claim.split("about ")[1].split()[0]))
    return _result(findings, evidence, {"coverage_calculated_count": len(findings)})


def _fast_moving_stock(tool_registry: ToolRegistry, item_code=None, warehouse=None, item_group=None, window_days: int = 90, turnover_threshold: float = 1.0) -> SkillResult:
    result = tool_registry.get_tool("inventory.get_item_movement")(item_code=item_code, warehouse=warehouse, item_group=item_group, window_days=window_days)
    if result.status != ToolStatus.OK:
        return SkillResult(status=SkillStatus.ERROR, error=result.error)
    evidence = Evidence("ev-item-movement", "inventory.get_item_movement", vars(result.query_meta) if result.query_meta else {}, result.data, f"{len(result.data)} stock movement record(s) over {window_days} days")
    findings = []
    for r in result.data:
        if r["stock"] <= 0 or r["qty_out_in_window"] <= 0:
            continue
        turnover = r["qty_out_in_window"] / r["stock"]
        if turnover >= turnover_threshold:
            findings.append(Finding(
                claim=(f"{r['item_code']} ({r['item_name']}) at {r['warehouse']} is a fast mover: {r['qty_out_in_window']:.0f} {r['uom']} "
                       f"issued in {window_days} days versus {r['stock']:.0f} currently in stock."),
                confidence=0.9 if turnover >= 2 else 0.75, supporting_evidence_ids=[evidence.id],
            ))
    return _result(findings, evidence, {"fast_moving_item_count": len(findings)})


SKILL = Skill("inventory.stock_balance", "Shows current inventory balance by item and warehouse, including stock, reservations, incoming and projected quantity.", ["stock balance", "current inventory", "how much stock do we have", "available quantity"], FILTER_PARAMS, ["inventory.get_stock_balance"], _stock_balance)
AVAILABLE_STOCK_SKILL = Skill("inventory.available_stock", "Shows stock available to promise after reservations are deducted.", ["available stock", "free stock", "reserved stock", "available to promise"], FILTER_PARAMS, ["inventory.get_stock_balance"], _available_stock)
NEGATIVE_STOCK_SKILL = Skill("inventory.negative_stock", "Finds item and warehouse combinations with negative inventory.", ["negative stock", "stock below zero", "negative inventory"], FILTER_PARAMS, ["inventory.get_stock_balance"], _negative_stock)
VALUATION_SKILL = Skill("inventory.inventory_valuation", "Shows inventory value and valuation rate by item and warehouse.", ["inventory value", "stock valuation", "highest value stock", "valuation rate"], FILTER_PARAMS, ["inventory.get_stock_balance"], _inventory_valuation)
WAREHOUSE_IMBALANCE_SKILL = Skill("inventory.warehouse_imbalance", "Finds items unevenly distributed across warehouses and suggests transfer review.", ["warehouse imbalance", "transfer stock", "move stock between warehouses", "uneven warehouse stock"], [SkillParam("item_code", "str", required=False), SkillParam("item_group", "str", required=False), SkillParam("concentration_threshold_pct", "float", required=False, default=80.0)], ["inventory.get_stock_balance"], _warehouse_imbalance)
COVERAGE_SKILL = Skill("inventory.stock_coverage", "Estimates how many days current inventory will last from recent consumption.", ["stock coverage", "days of inventory", "how long will stock last", "inventory days"], FILTER_PARAMS + [SkillParam("window_days", "int", required=False, default=90)], ["inventory.get_item_movement"], _stock_coverage)
FAST_MOVING_SKILL = Skill("inventory.fast_moving_stock", "Finds items with high recent consumption compared with stock on hand.", ["fast moving stock", "fast movers", "high consumption items", "inventory turnover"], FILTER_PARAMS + [SkillParam("window_days", "int", required=False, default=90), SkillParam("turnover_threshold", "float", required=False, default=1.0)], ["inventory.get_item_movement"], _fast_moving_stock)
