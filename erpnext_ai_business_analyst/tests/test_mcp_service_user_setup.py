"""
Tests for setup/mcp_service_user.py's doctype-union logic. The actual
User/Role creation (create_mcp_service_user) is a real side-effect meant
to be run once deliberately — not exercised on every test run — so only
the pure _required_doctypes() logic is tested here.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_mcp_service_user_setup
"""

from __future__ import annotations

import unittest

from erpnext_ai_business_analyst.setup.mcp_service_user import _required_doctypes
from erpnext_ai_business_analyst.tools.inventory.item_movement import (
    REQUIRED_READ_DOCTYPES as ITEM_MOVEMENT_DOCTYPES,
)
from erpnext_ai_business_analyst.tools.inventory.reorder import (
    REQUIRED_READ_DOCTYPES as REORDER_DOCTYPES,
)


class TestRequiredDoctypes(unittest.TestCase):
    def test_is_union_of_both_tools_doctypes(self):
        result = set(_required_doctypes())
        expected = set(REORDER_DOCTYPES) | set(ITEM_MOVEMENT_DOCTYPES)
        self.assertEqual(result, expected)

    def test_contains_no_duplicates(self):
        result = _required_doctypes()
        self.assertEqual(len(result), len(set(result)))

    def test_is_sorted_for_stable_output(self):
        result = _required_doctypes()
        self.assertEqual(result, sorted(result))