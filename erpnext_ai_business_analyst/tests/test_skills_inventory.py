"""
Tests for skills/inventory/*.

Calls Skill.run() directly against ToolRegistry — no planner involved yet,
per MVP_PLAN.md Step 7. Uses the same rollback-per-test isolation as
test_tools_inventory.py.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_skills_inventory
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_ai_business_analyst.skills.base import SkillStatus
from erpnext_ai_business_analyst.skills.inventory.reorder_demand import SKILL as REORDER_DEMAND_SKILL
from erpnext_ai_business_analyst.skills.inventory.stockout_risk import SKILL as STOCKOUT_RISK_SKILL
from erpnext_ai_business_analyst.skills.inventory.dead_stock import SKILL as DEAD_STOCK_SKILL
from erpnext_ai_business_analyst.skills.inventory.slow_moving_stock import SKILL as SLOW_MOVING_STOCK_SKILL
from erpnext_ai_business_analyst.tools.registry import ToolRegistry
from erpnext_ai_business_analyst.tests.fixtures import (
    create_bin,
    create_item,
    create_material_request,
    create_purchase_order,
    create_warehouse,
    get_or_create_company,
    insert_sle,
)


def _tool_registry() -> ToolRegistry:
    return ToolRegistry.get()


# ---------------------------------------------------------------------------
# inventory.reorder_demand
# ---------------------------------------------------------------------------

class TestReorderDemandSkill(FrappeTestCase):
    def test_triggered_item_with_no_pending_gets_high_confidence(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)
        item_code = create_item(suffix, reorder_rows=[{
            "warehouse": warehouse,
            "warehouse_reorder_level": 300,
            "warehouse_reorder_qty": 50,
        }])
        insert_sle(item_code, warehouse, qty_after_transaction=100,
                   actual_qty=100, days_ago=1, voucher_no=f"AI-TEST-SLE-{suffix}")

        result = REORDER_DEMAND_SKILL.run(
            _tool_registry(), item_code=item_code, warehouse=warehouse, item_group=None
        )

        self.assertEqual(result.status, SkillStatus.OK)
        self.assertEqual(len(result.findings), 1)
        self.assertAlmostEqual(result.findings[0].confidence, 0.9)
        self.assertIn("no pending PR, STR, or PO", result.findings[0].claim)
        self.assertEqual(result.metrics["triggered_item_count"], 1)

    def test_triggered_item_with_pending_gets_lower_confidence(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)
        item_code = create_item(suffix, reorder_rows=[{
            "warehouse": warehouse,
            "warehouse_reorder_level": 500,
            "warehouse_reorder_qty": 50,
        }])
        insert_sle(item_code, warehouse, qty_after_transaction=100,
                   actual_qty=100, days_ago=1, voucher_no=f"AI-TEST-SLE-{suffix}")
        create_purchase_order(item_code, warehouse, qty=50, suffix=suffix)

        result = REORDER_DEMAND_SKILL.run(
            _tool_registry(), item_code=item_code, warehouse=warehouse, item_group=None
        )

        self.assertEqual(result.status, SkillStatus.OK)
        self.assertAlmostEqual(result.findings[0].confidence, 0.6)

    def test_no_data_when_nothing_triggered(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)
        item_code = create_item(suffix, reorder_rows=[{
            "warehouse": warehouse,
            "warehouse_reorder_level": 10,
            "warehouse_reorder_qty": 5,
        }])
        insert_sle(item_code, warehouse, qty_after_transaction=1000,
                   actual_qty=1000, days_ago=1, voucher_no=f"AI-TEST-SLE-{suffix}")

        result = REORDER_DEMAND_SKILL.run(
            _tool_registry(), item_code=item_code, warehouse=warehouse, item_group=None
        )

        self.assertEqual(result.status, SkillStatus.NO_DATA)
        self.assertEqual(result.metrics["triggered_item_count"], 0)


# ---------------------------------------------------------------------------
# inventory.stockout_risk
# ---------------------------------------------------------------------------

class TestStockoutRiskSkill(FrappeTestCase):
    def test_ranks_by_days_to_stockout_with_unclear_last(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)

        rol_rows = lambda: [{
            "warehouse": warehouse, "warehouse_reorder_level": 1000, "warehouse_reorder_qty": 50,
        }]

        item_a = create_item(f"{suffix}-a", reorder_rows=rol_rows())
        create_bin(item_a, warehouse, actual_qty=50)
        insert_sle(item_a, warehouse, qty_after_transaction=50,
                   actual_qty=50, days_ago=1, voucher_no=f"AI-TEST-A-CUR-{suffix}")
        insert_sle(item_a, warehouse, qty_after_transaction=950,
                   actual_qty=-900, days_ago=10, voucher_no=f"AI-TEST-A-CONS-{suffix}")

        item_b = create_item(f"{suffix}-b", reorder_rows=rol_rows())
        create_bin(item_b, warehouse, actual_qty=200)
        insert_sle(item_b, warehouse, qty_after_transaction=200,
                   actual_qty=200, days_ago=1, voucher_no=f"AI-TEST-B-CUR-{suffix}")
        insert_sle(item_b, warehouse, qty_after_transaction=380,
                   actual_qty=-180, days_ago=15, voucher_no=f"AI-TEST-B-CONS-{suffix}")

        item_c = create_item(f"{suffix}-c", reorder_rows=rol_rows())
        create_bin(item_c, warehouse, actual_qty=80)
        insert_sle(item_c, warehouse, qty_after_transaction=80,
                   actual_qty=80, days_ago=1, voucher_no=f"AI-TEST-C-CUR-{suffix}")

        result = STOCKOUT_RISK_SKILL.run(_tool_registry(), warehouse=warehouse, item_code=None, item_group=None)

        self.assertEqual(result.status, SkillStatus.OK)
        self.assertEqual(len(result.findings), 3)
        self.assertEqual(result.metrics, {"critical": 1, "high": 0, "medium": 0, "low": 1, "unclear": 1})
        self.assertIn("CRITICAL", result.findings[0].claim)
        self.assertIn("LOW", result.findings[1].claim)
        self.assertIn("unclear", result.findings[2].claim)

    def test_no_data_when_nothing_below_rol(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)
        item_code = create_item(suffix, reorder_rows=[{
            "warehouse": warehouse, "warehouse_reorder_level": 10, "warehouse_reorder_qty": 5,
        }])
        create_bin(item_code, warehouse, actual_qty=1000)
        insert_sle(item_code, warehouse, qty_after_transaction=1000,
                   actual_qty=1000, days_ago=1, voucher_no=f"AI-TEST-SLE-{suffix}")

        result = STOCKOUT_RISK_SKILL.run(_tool_registry(), warehouse=warehouse, item_code=None, item_group=None)

        self.assertEqual(result.status, SkillStatus.NO_DATA)


# ---------------------------------------------------------------------------
# inventory.dead_stock
# ---------------------------------------------------------------------------

class TestDeadStockSkill(FrappeTestCase):
    def test_classifies_long_dead_dead_and_no_history(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)

        # A — long-dead: last moved 200 days ago (>= 90*2).
        item_a = create_item(f"{suffix}-a")
        create_bin(item_a, warehouse, actual_qty=10)
        insert_sle(item_a, warehouse, qty_after_transaction=10,
                   actual_qty=10, days_ago=200, voucher_no=f"AI-TEST-A-{suffix}")

        # B — dead (not long-dead): last moved 100 days ago (>= 90, < 180).
        item_b = create_item(f"{suffix}-b")
        create_bin(item_b, warehouse, actual_qty=10)
        insert_sle(item_b, warehouse, qty_after_transaction=10,
                   actual_qty=10, days_ago=100, voucher_no=f"AI-TEST-B-{suffix}")

        # C — no movement history at all (Bin exists, no SLE ever).
        item_c = create_item(f"{suffix}-c")
        create_bin(item_c, warehouse, actual_qty=10)

        # D — recently moved, should be excluded entirely.
        item_d = create_item(f"{suffix}-d")
        create_bin(item_d, warehouse, actual_qty=10)
        insert_sle(item_d, warehouse, qty_after_transaction=10,
                   actual_qty=10, days_ago=5, voucher_no=f"AI-TEST-D-{suffix}")

        result = DEAD_STOCK_SKILL.run(
            _tool_registry(), warehouse=warehouse, item_code=None, item_group=None, days_threshold=90
        )

        self.assertEqual(result.status, SkillStatus.OK)
        self.assertEqual(len(result.findings), 3)
        self.assertEqual(result.metrics["dead_item_count"], 3)

        self.assertIn("long-dead", result.findings[0].claim)
        self.assertAlmostEqual(result.findings[0].confidence, 0.9)

        self.assertIn("(dead)", result.findings[1].claim)
        self.assertAlmostEqual(result.findings[1].confidence, 0.7)

        self.assertIn("no movement history found", result.findings[2].claim)
        self.assertAlmostEqual(result.findings[2].confidence, 0.8)

        self.assertEqual(len(result.suggested_next_skills), 1)
        self.assertEqual(result.suggested_next_skills[0].skill_name, "inventory.overstock")

    def test_no_data_when_nothing_dead(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)
        item_code = create_item(suffix)
        create_bin(item_code, warehouse, actual_qty=10)
        insert_sle(item_code, warehouse, qty_after_transaction=10,
                   actual_qty=10, days_ago=5, voucher_no=f"AI-TEST-{suffix}")

        result = DEAD_STOCK_SKILL.run(
            _tool_registry(), warehouse=warehouse, item_code=None, item_group=None, days_threshold=90
        )

        self.assertEqual(result.status, SkillStatus.NO_DATA)
        self.assertEqual(result.metrics["dead_item_count"], 0)


# ---------------------------------------------------------------------------
# inventory.slow_moving_stock
# ---------------------------------------------------------------------------

class TestSlowMovingStockSkill(FrappeTestCase):
    def test_flags_severe_and_moderate_excludes_fast_and_dead(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)

        # E — severe: stock 1000, consumed 100 over 90 days -> ~900 days coverage.
        item_e = create_item(f"{suffix}-e")
        create_bin(item_e, warehouse, actual_qty=1000)
        insert_sle(item_e, warehouse, qty_after_transaction=1000,
                   actual_qty=1000, days_ago=1, voucher_no=f"AI-TEST-E-CUR-{suffix}")
        insert_sle(item_e, warehouse, qty_after_transaction=1100,
                   actual_qty=-100, days_ago=10, voucher_no=f"AI-TEST-E-CONS-{suffix}")

        # F — moderate: stock 200, consumed 80 over 90 days -> ~225 days coverage.
        item_f = create_item(f"{suffix}-f")
        create_bin(item_f, warehouse, actual_qty=200)
        insert_sle(item_f, warehouse, qty_after_transaction=200,
                   actual_qty=200, days_ago=1, voucher_no=f"AI-TEST-F-CUR-{suffix}")
        insert_sle(item_f, warehouse, qty_after_transaction=280,
                   actual_qty=-80, days_ago=10, voucher_no=f"AI-TEST-F-CONS-{suffix}")

        # G — fast mover: stock 50, consumed 500 over 90 days -> ~9 days coverage. Excluded.
        item_g = create_item(f"{suffix}-g")
        create_bin(item_g, warehouse, actual_qty=50)
        insert_sle(item_g, warehouse, qty_after_transaction=50,
                   actual_qty=50, days_ago=1, voucher_no=f"AI-TEST-G-CUR-{suffix}")
        insert_sle(item_g, warehouse, qty_after_transaction=550,
                   actual_qty=-500, days_ago=10, voucher_no=f"AI-TEST-G-CONS-{suffix}")

        # H — zero movement at all. Dead Stock's territory, must be excluded here.
        item_h = create_item(f"{suffix}-h")
        create_bin(item_h, warehouse, actual_qty=10)

        result = SLOW_MOVING_STOCK_SKILL.run(
            _tool_registry(), warehouse=warehouse, item_code=None, item_group=None,
            window_days=90, coverage_days_threshold=180,
        )

        self.assertEqual(result.status, SkillStatus.OK)
        self.assertEqual(len(result.findings), 2)
        self.assertEqual(result.metrics["slow_moving_item_count"], 2)

        self.assertIn("severe", result.findings[0].claim)
        self.assertAlmostEqual(result.findings[0].confidence, 0.9)

        self.assertIn("moderate", result.findings[1].claim)
        self.assertAlmostEqual(result.findings[1].confidence, 0.6)

    def test_no_data_when_nothing_slow(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)
        item_code = create_item(suffix)
        create_bin(item_code, warehouse, actual_qty=50)
        insert_sle(item_code, warehouse, qty_after_transaction=50,
                   actual_qty=50, days_ago=1, voucher_no=f"AI-TEST-CUR-{suffix}")
        insert_sle(item_code, warehouse, qty_after_transaction=550,
                   actual_qty=-500, days_ago=10, voucher_no=f"AI-TEST-CONS-{suffix}")

        result = SLOW_MOVING_STOCK_SKILL.run(
            _tool_registry(), warehouse=warehouse, item_code=None, item_group=None,
            window_days=90, coverage_days_threshold=180,
        )

        self.assertEqual(result.status, SkillStatus.NO_DATA)
        self.assertEqual(result.metrics["slow_moving_item_count"], 0)