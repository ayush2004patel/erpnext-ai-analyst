"""
Tests for tools/inventory/*.

Uses FrappeTestCase, which wraps each test method in a DB transaction and
rolls it back automatically — no permanent site data is left behind, no
separate fixture framework needed. Test records are created inline per
test with unique suffixes to avoid collisions across runs.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_tools_inventory
"""

from __future__ import annotations

import os
import re

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from erpnext_ai_business_analyst.tests.fixtures import (
    create_bin,
    create_item,
    create_material_request,
    create_purchase_order,
    create_warehouse,
    get_or_create_company,
    insert_sle,
)
from erpnext_ai_business_analyst.tools.inventory.item_movement import TOOL as ITEM_MOVEMENT_TOOL
from erpnext_ai_business_analyst.tools.inventory.reorder import TOOL as REORDER_TOOL
from erpnext_ai_business_analyst.tools.base import ToolStatus

# ---------------------------------------------------------------------------
# inventory.get_reorder_status
# ---------------------------------------------------------------------------

class TestGetReorderStatus(FrappeTestCase):
    def test_projected_and_trigger_qty(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)

        # ROL=300, ROQ=50 — chosen so projected_qty (160) lands below ROL,
        # exercising the GREATEST(...) branch of the trigger_qty formula.
        item_code = create_item(suffix, reorder_rows=[{
            "warehouse": warehouse,
            "warehouse_reorder_level": 300,
            "warehouse_reorder_qty": 50,
        }])

        insert_sle(item_code, warehouse, qty_after_transaction=100,
                    actual_qty=100, days_ago=1, voucher_no=f"AI-TEST-SLE-{suffix}")
        create_material_request(item_code, warehouse, qty=30, mr_type="Purchase")
        create_material_request(item_code, warehouse, qty=10, mr_type="Material Transfer")
        create_purchase_order(item_code, warehouse, qty=20, suffix=suffix)

        result = REORDER_TOOL(item_code=item_code, warehouse=warehouse)

        self.assertEqual(result.status, ToolStatus.OK)
        self.assertEqual(result.query_meta.row_count, 1)
        row = result.data[0]

        self.assertEqual(row["stock"], 100)
        self.assertEqual(row["pending_pr"], 30)
        self.assertEqual(row["pending_str"], 10)
        self.assertEqual(row["pending_po"], 20)
        self.assertEqual(row["projected_qty"], 160)          # 100+30+10+20
        self.assertEqual(row["trigger_qty"], 140)             # max(300-160, 50)

    def test_missing_reorder_config_returns_no_rows(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = create_warehouse(get_or_create_company(), suffix)
        item_code = create_item(suffix)  # no reorder_levels row

        result = REORDER_TOOL(item_code=item_code, warehouse=warehouse)

        self.assertEqual(result.status, ToolStatus.OK)
        self.assertEqual(result.query_meta.row_count, 0)


# ---------------------------------------------------------------------------
# inventory.get_item_movement
# ---------------------------------------------------------------------------

class TestGetItemMovement(FrappeTestCase):
    def test_last_movement_and_window_sums(self):
        suffix = frappe.generate_hash(length=6)
        company = get_or_create_company()
        warehouse = create_warehouse(company, suffix)
        item_code = create_item(suffix)

        frappe.get_doc({
            "doctype": "Bin",
            "item_code": item_code,
            "warehouse": warehouse,
            "actual_qty": 5,
            "stock_uom": "Nos",
        }).insert(ignore_permissions=True)

        # Old movement, outside the 90-day window.
        insert_sle(item_code, warehouse, qty_after_transaction=25,
                    actual_qty=-15, days_ago=200, voucher_no=f"AI-TEST-SLE-OLD-{suffix}")
        # Recent movement, inside the window — this should be the last_movement_date.
        insert_sle(item_code, warehouse, qty_after_transaction=5,
                    actual_qty=-20, days_ago=5, voucher_no=f"AI-TEST-SLE-NEW-{suffix}")

        result = ITEM_MOVEMENT_TOOL(item_code=item_code, warehouse=warehouse, window_days=90)

        self.assertEqual(result.status, ToolStatus.OK)
        row = result.data[0]

        self.assertEqual(row["qty_out_in_window"], 20)   # only the -5-day entry
        self.assertEqual(row["movement_count_in_window"], 1)
        self.assertLessEqual(row["days_since_last_movement"], 6)
        self.assertGreaterEqual(row["days_since_last_movement"], 4)

    def test_min_days_since_movement_filter(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = create_warehouse(get_or_create_company(), suffix)
        item_code = create_item(suffix)

        frappe.get_doc({
            "doctype": "Bin",
            "item_code": item_code,
            "warehouse": warehouse,
            "actual_qty": 5,
            "stock_uom": "Nos",
        }).insert(ignore_permissions=True)
        insert_sle(item_code, warehouse, qty_after_transaction=5,
                    actual_qty=-5, days_ago=5, voucher_no=f"AI-TEST-SLE-{suffix}")

        # Item moved 5 days ago — should NOT show up when asking for 90+ day dead stock.
        result = ITEM_MOVEMENT_TOOL(item_code=item_code, warehouse=warehouse,
                                     min_days_since_movement=90)
        self.assertEqual(result.query_meta.row_count, 0)


# ---------------------------------------------------------------------------
# No-side-effects lint — applies to every file under tools/, current and future.
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    r"\.save\(",
    r"\.submit\(",
    r"\.cancel\(",
    r"\.delete\(",
    r"\.db_set\(",
    r"frappe\.delete_doc",
    r"\.db_insert\(",   # tools themselves must never write — only tests use this
]

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tools"
)


class TestToolsHaveNoSideEffects(FrappeTestCase):
    def test_no_write_calls_in_tools_directory(self):
        violations = []
        for root, _dirs, files in os.walk(TOOLS_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(root, fname)
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                for pattern in FORBIDDEN_PATTERNS:
                    if re.search(pattern, content):
                        violations.append(f"{path}: matched {pattern!r}")

        self.assertEqual(violations, [], "Write calls found in tools/:\n" + "\n".join(violations))