"""
Tests for api.ask_question — the whitelisted entry point the chat UI calls.

OllamaClient is patched out at the api module level so this never makes a
real Ollama call; ScriptedLLMClient (same fake used for planner tests)
drives the decisions instead.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_api
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_ai_business_analyst import api
from erpnext_ai_business_analyst.tests.fixtures import (
    create_bin,
    create_item,
    create_warehouse,
    get_or_create_company,
    insert_sle,
)
from erpnext_ai_business_analyst.tests.llm_fakes import ScriptedLLMClient

RUN_DEAD_STOCK = '{"action": "RUN", "skill_name": "inventory.dead_stock", "inputs": {}}'
CONCLUDE_CONVERSATIONAL = '{"action": "CONCLUDE", "category": "conversational"}'
CONCLUDE_MID_CHAIN = '{"action": "CONCLUDE"}'  # valid only when history is non-empty


def _make_dead_stock_item(suffix: str) -> str:
    company = get_or_create_company()
    warehouse = create_warehouse(company, suffix)
    item_code = create_item(suffix, reorder_rows=[{
        "warehouse": warehouse, "warehouse_reorder_level": 50, "warehouse_reorder_qty": 10,
    }])
    create_bin(item_code, warehouse, actual_qty=310)
    insert_sle(item_code, warehouse, qty_after_transaction=310,
               actual_qty=310, days_ago=200, voucher_no=f"AI-TEST-{suffix}")
    return warehouse


class TestAskQuestion(FrappeTestCase):
    def test_returns_structured_result_with_findings(self):
        suffix = frappe.generate_hash(length=6)
        # Fixture item isn't warehouse-scoped in the API call (ask_question
        # doesn't take initial_inputs), so the dead_stock Skill runs across
        # all warehouses on the site — the test item still gets found.
        _make_dead_stock_item(suffix)

        with patch("erpnext_ai_business_analyst.api.OllamaClient",
                    return_value=ScriptedLLMClient([RUN_DEAD_STOCK, CONCLUDE_MID_CHAIN])):
            response = api.ask_question(question="Which inventory has not moved for 90 days?")

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["steps"], [{"skill_name": "inventory.dead_stock", "status": "ok"}])
        self.assertGreaterEqual(len(response["findings"]), 1)
        self.assertIn("confidence", response["findings"][0])
        self.assertIn("claim", response["findings"][0])
        self.assertEqual(response["decision_errors"], [])
        self.assertTrue(response["log_name"])

        # The log_name should reference a real, persisted AI Investigation Log.
        log_doc = frappe.get_doc("AI Investigation Log", response["log_name"])
        self.assertEqual(log_doc.status, "ok")

    def test_llm_concludes_with_conversational_category(self):
        with patch("erpnext_ai_business_analyst.api.OllamaClient",
                    return_value=ScriptedLLMClient([CONCLUDE_CONVERSATIONAL])):
            response = api.ask_question(question="How are you?")

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["steps"], [])
        self.assertEqual(response["findings"], [])
        self.assertEqual(response["category"], "conversational")
        self.assertTrue(response["log_name"])

    def test_llm_concludes_with_no_matching_skill_category(self):
        conclude_no_match = '{"action": "CONCLUDE", "category": "no_matching_skill"}'
        with patch("erpnext_ai_business_analyst.api.OllamaClient",
                    return_value=ScriptedLLMClient([conclude_no_match])):
            response = api.ask_question(question="How many items are in my item master?")

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["steps"], [])
        self.assertEqual(response["findings"], [])
        self.assertEqual(response["category"], "no_matching_skill")
        self.assertTrue(response["log_name"])

    def test_empty_question_raises(self):
        with patch("erpnext_ai_business_analyst.api.OllamaClient",
                    return_value=ScriptedLLMClient([CONCLUDE_CONVERSATIONAL])):
            with self.assertRaises(frappe.exceptions.ValidationError):
                api.ask_question(question="   ")