"""Tests for the core stock-control inventory skills."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_ai_business_analyst.skills.base import SkillStatus
from erpnext_ai_business_analyst.skills.inventory.stock_control import (
    AVAILABLE_STOCK_SKILL,
    NEGATIVE_STOCK_SKILL,
    SKILL as STOCK_BALANCE_SKILL,
)
from erpnext_ai_business_analyst.tests.fixtures import create_bin, create_item, create_warehouse, get_or_create_company
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


class TestStockControlSkills(FrappeTestCase):
    def test_stock_balance_and_available_stock_use_bin_quantities(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = create_warehouse(get_or_create_company(), suffix)
        item_code = create_item(suffix)
        create_bin(item_code, warehouse, actual_qty=20)
        frappe.db.set_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "reserved_qty", 5)

        stock = STOCK_BALANCE_SKILL.run(ToolRegistry.get(), item_code=item_code, warehouse=warehouse, item_group=None)
        available = AVAILABLE_STOCK_SKILL.run(ToolRegistry.get(), item_code=item_code, warehouse=warehouse, item_group=None)

        self.assertEqual(stock.status, SkillStatus.OK)
        self.assertIn("20", stock.findings[0].claim)
        self.assertEqual(available.status, SkillStatus.OK)
        self.assertIn("15", available.findings[0].claim)

    def test_negative_stock_is_flagged(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = create_warehouse(get_or_create_company(), suffix)
        item_code = create_item(suffix)
        create_bin(item_code, warehouse, actual_qty=-3)

        result = NEGATIVE_STOCK_SKILL.run(ToolRegistry.get(), item_code=item_code, warehouse=warehouse, item_group=None)

        self.assertEqual(result.status, SkillStatus.OK)
        self.assertEqual(result.metrics["negative_stock_count"], 1)
