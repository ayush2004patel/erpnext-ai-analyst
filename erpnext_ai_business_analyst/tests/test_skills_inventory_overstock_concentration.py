"""
Tests for inventory.overstock and inventory.inventory_concentration.

Split from test_skills_inventory.py to keep each file focused — that file
already covers reorder_demand, stockout_risk, dead_stock, slow_moving_stock.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_skills_inventory_overstock_concentration
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_ai_business_analyst.skills.base import SkillStatus
from erpnext_ai_business_analyst.skills.inventory.overstock import SKILL as OVERSTOCK_SKILL
from erpnext_ai_business_analyst.skills.inventory.inventory_concentration import (
    SKILL as CONCENTRATION_SKILL,
)
from erpnext_ai_business_analyst.tools.registry import ToolRegistry
from erpnext_ai_business_analyst.tests.fixtures import (
    create_bin,
    create_item,
    create_item_group,
    create_warehouse,
    get_or_create_company,
    insert_sle,
)


def _tool_registry() -> ToolRegistry:
    return ToolRegistry.get()


# ---------------------------------------------------------------------------
# inventory.overstock
# ---------------------------------------------------------------------------

class TestOverstockSkill(FrappeTestCase):
    def test_flags_at_boundary_and_severe_excludes_below(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)

        # P — exactly at the default multiplier boundary: stock=150, ROL=50 -> ratio 3.0.
        item_p = create_item(f"{suffix}-p", reorder_rows=[{
            "warehouse": warehouse, "warehouse_reorder_level": 50, "warehouse_reorder_qty": 10,
        }])
        insert_sle(item_p, warehouse, qty_after_transaction=150,
                   actual_qty=150, days_ago=1, voucher_no=f"AI-TEST-P-{suffix}")

        # Q — just below boundary: stock=149, ROL=50 -> ratio 2.98. Excluded.
        item_q = create_item(f"{suffix}-q", reorder_rows=[{
            "warehouse": warehouse, "warehouse_reorder_level": 50, "warehouse_reorder_qty": 10,
        }])
        insert_sle(item_q, warehouse, qty_after_transaction=149,
                   actual_qty=149, days_ago=1, voucher_no=f"AI-TEST-Q-{suffix}")

        # R — severe: stock=310, ROL=50 -> ratio 6.2 (>= multiplier * 2.0 = 6.0).
        item_r = create_item(f"{suffix}-r", reorder_rows=[{
            "warehouse": warehouse, "warehouse_reorder_level": 50, "warehouse_reorder_qty": 10,
        }])
        insert_sle(item_r, warehouse, qty_after_transaction=310,
                   actual_qty=310, days_ago=1, voucher_no=f"AI-TEST-R-{suffix}")

        result = OVERSTOCK_SKILL.run(
            _tool_registry(), warehouse=warehouse, item_code=None, item_group=None,
            overstock_multiplier=3.0, window_days=90,
        )

        self.assertEqual(result.status, SkillStatus.OK)
        self.assertEqual(len(result.findings), 2)  # P and R only, Q excluded
        self.assertEqual(result.metrics["overstocked_item_count"], 2)

        # Sorted descending by ratio: R (6.2, severe) first, P (3.0, flagged) second.
        self.assertIn("severe", result.findings[0].claim)
        self.assertAlmostEqual(result.findings[0].confidence, 0.9)

        self.assertIn("flagged", result.findings[1].claim)
        self.assertAlmostEqual(result.findings[1].confidence, 0.7)

        self.assertEqual(len(result.suggested_next_skills), 1)
        self.assertEqual(result.suggested_next_skills[0].skill_name, "inventory.slow_moving_stock")

    def test_no_data_when_nothing_overstocked(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)
        item_code = create_item(suffix, reorder_rows=[{
            "warehouse": warehouse, "warehouse_reorder_level": 50, "warehouse_reorder_qty": 10,
        }])
        # ratio 2.0 — below the default 3.0 multiplier.
        insert_sle(item_code, warehouse, qty_after_transaction=100,
                   actual_qty=100, days_ago=1, voucher_no=f"AI-TEST-{suffix}")

        result = OVERSTOCK_SKILL.run(
            _tool_registry(), warehouse=warehouse, item_code=None, item_group=None,
            overstock_multiplier=3.0, window_days=90,
        )

        self.assertEqual(result.status, SkillStatus.NO_DATA)
        self.assertEqual(result.metrics["overstocked_item_count"], 0)


# ---------------------------------------------------------------------------
# inventory.inventory_concentration
# ---------------------------------------------------------------------------

class TestInventoryConcentrationSkill(FrappeTestCase):
    def test_flags_at_and_above_threshold_excludes_below_and_single_warehouse(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        item_group = create_item_group(suffix)
        wh1 = create_warehouse(company, f"{suffix}-1")
        wh2 = create_warehouse(company, f"{suffix}-2")

        # X — exactly at the 80% boundary: 80 in wh1, 20 in wh2 -> 80.0%.
        item_x = create_item(f"{suffix}-x", item_group=item_group)
        create_bin(item_x, wh1, actual_qty=80)
        create_bin(item_x, wh2, actual_qty=20)

        # Y — severe: 96 in wh1, 4 in wh2 -> 96.0% (>= 95 severe cutoff).
        item_y = create_item(f"{suffix}-y", item_group=item_group)
        create_bin(item_y, wh1, actual_qty=96)
        create_bin(item_y, wh2, actual_qty=4)

        # Z — just below boundary: 79 in wh1, 21 in wh2 -> 79.0%. Excluded.
        item_z = create_item(f"{suffix}-z", item_group=item_group)
        create_bin(item_z, wh1, actual_qty=79)
        create_bin(item_z, wh2, actual_qty=21)

        # W — single warehouse only. Excluded regardless of "100%" implied concentration.
        item_w = create_item(f"{suffix}-w", item_group=item_group)
        create_bin(item_w, wh1, actual_qty=50)

        result = CONCENTRATION_SKILL.run(
            _tool_registry(), item_code=None, item_group=item_group,
            concentration_threshold_pct=80.0,
        )

        self.assertEqual(result.status, SkillStatus.OK)
        self.assertEqual(len(result.findings), 2)  # X and Y only
        self.assertEqual(result.metrics["concentrated_item_count"], 2)
        self.assertEqual(result.metrics["evaluated_multi_warehouse_item_count"], 3)  # X, Y, Z (not W)

        # Sorted descending by concentration_pct: Y (96%, severe) first, X (80%, flagged) second.
        self.assertIn("severe", result.findings[0].claim)
        self.assertAlmostEqual(result.findings[0].confidence, 0.9)

        self.assertIn("flagged", result.findings[1].claim)
        self.assertAlmostEqual(result.findings[1].confidence, 0.7)

        self.assertEqual(len(result.evidence), 2)
        evidence_ids = {e.id for e in result.evidence}
        self.assertEqual(evidence_ids, {"ev-movement", "ev-concentration"})

    def test_no_data_when_evenly_spread(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        item_group = create_item_group(suffix)
        wh1 = create_warehouse(company, f"{suffix}-1")
        wh2 = create_warehouse(company, f"{suffix}-2")

        item_code = create_item(suffix, item_group=item_group)
        create_bin(item_code, wh1, actual_qty=50)
        create_bin(item_code, wh2, actual_qty=50)  # 50/50 split -> 50% concentration

        result = CONCENTRATION_SKILL.run(
            _tool_registry(), item_code=None, item_group=item_group,
            concentration_threshold_pct=80.0,
        )

        self.assertEqual(result.status, SkillStatus.NO_DATA)
        self.assertEqual(result.metrics["concentrated_item_count"], 0)