"""
Tests for the AI Investigation Log / AI Investigation Step DocTypes.

Step 10 scope only: verifies the DocTypes themselves work correctly
(creation, child table, JSON field round-trip, mandatory field
enforcement). Nothing here calls the planner — that's Step 11.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_investigation_log_doctype
"""

from __future__ import annotations

import json

import frappe
from frappe.tests.utils import FrappeTestCase


class TestAIInvestigationLogDoctype(FrappeTestCase):
    def test_create_log_with_steps_and_json_fields_round_trip(self):
        doc = frappe.get_doc({
            "doctype": "AI Investigation Log",
            "question": "Which inventory has not moved for 90 days?",
            "status": "ok",
            "hop_count": 2,
            "metrics": {
                "inventory.dead_stock": {"dead_item_count": 1},
                "inventory.overstock": {"overstocked_item_count": 1},
            },
            "decision_errors": frappe.as_json([]),
            "steps": [
                {
                    "skill_name": "inventory.dead_stock",
                    "status": "ok",
                    "inputs": {"warehouse": "AI Test WH - A"},
                    "findings": frappe.as_json([
                        {"claim": "Item X is dead stock", "confidence": 0.9,
                         "supporting_evidence_ids": ["ev-movement"]},
                    ]),
                    "metrics": {"dead_item_count": 1},
                    "evidence": frappe.as_json([
                        {"id": "ev-movement", "source_tool": "inventory.get_item_movement",
                         "query_meta": {"doctype": "Bin", "row_count": 1},
                         "records": [{"item_code": "X"}], "summary": "1 item"},
                    ]),
                },
                {
                    "skill_name": "inventory.overstock",
                    "status": "no_data",
                    "inputs": {"warehouse": "AI Test WH - A"},
                    "findings": frappe.as_json([]),
                    "metrics": {"overstocked_item_count": 0},
                    "evidence": frappe.as_json([]),
                },
            ],
        })
        doc.insert(ignore_permissions=True)

        reloaded = frappe.get_doc("AI Investigation Log", doc.name)

        self.assertEqual(reloaded.question, "Which inventory has not moved for 90 days?")
        self.assertEqual(reloaded.status, "ok")
        self.assertEqual(reloaded.hop_count, 2)
        self.assertEqual(reloaded.user, "Administrator")  # default "user" -> session user
        self.assertIsNotNone(reloaded.timestamp)

        # JSON fields don't auto-decode on read — Frappe stores/returns the
        # raw JSON string; only writing a dict gets auto-encoded, not the
        # reverse. Parse explicitly (this applies to Step 11's planner
        # integration too, not just this test).
        self.assertEqual(
            json.loads(reloaded.metrics),
            {
                "inventory.dead_stock": {"dead_item_count": 1},
                "inventory.overstock": {"overstocked_item_count": 1},
            },
        )
        self.assertEqual(json.loads(reloaded.decision_errors), [])

        self.assertEqual(len(reloaded.steps), 2)
        step_1 = reloaded.steps[0]
        self.assertEqual(step_1.skill_name, "inventory.dead_stock")
        self.assertEqual(step_1.status, "ok")
        self.assertEqual(json.loads(step_1.inputs), {"warehouse": "AI Test WH - A"})
        step_1_findings = json.loads(step_1.findings)
        self.assertEqual(step_1_findings[0]["claim"], "Item X is dead stock")
        self.assertAlmostEqual(step_1_findings[0]["confidence"], 0.9)
        step_1_evidence = json.loads(step_1.evidence)
        self.assertEqual(step_1_evidence[0]["source_tool"], "inventory.get_item_movement")

        step_2 = reloaded.steps[1]
        self.assertEqual(step_2.skill_name, "inventory.overstock")
        self.assertEqual(step_2.status, "no_data")
        self.assertEqual(json.loads(step_2.findings), [])

    def test_missing_question_raises_mandatory_error(self):
        doc = frappe.get_doc({
            "doctype": "AI Investigation Log",
            "status": "ok",
        })
        with self.assertRaises(frappe.exceptions.MandatoryError):
            doc.insert(ignore_permissions=True)

    def test_missing_status_defaults_to_first_select_option(self):
        # Select fields in Frappe silently fall back to their first option
        # when left unset, even with reqd=1 — MandatoryError can never fire
        # for a Select field this way (unlike Data/Small Text). "ok" is the
        # first option in status's options list, so that's what a caller
        # gets if they forget to set it. Not a bug — documenting the real
        # behavior instead of asserting a false expectation.
        doc = frappe.get_doc({
            "doctype": "AI Investigation Log",
            "question": "Some question",
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.status, "ok")

    def test_log_without_steps_is_valid(self):
        # A "no_skill_matched" investigation has no steps at all.
        doc = frappe.get_doc({
            "doctype": "AI Investigation Log",
            "question": "What's the weather today?",
            "status": "no_skill_matched",
            "hop_count": 0,
        })
        doc.insert(ignore_permissions=True)

        reloaded = frappe.get_doc("AI Investigation Log", doc.name)
        self.assertEqual(reloaded.status, "no_skill_matched")
        self.assertEqual(len(reloaded.steps), 0)

    def test_step_missing_skill_name_raises_mandatory_error(self):
        doc = frappe.get_doc({
            "doctype": "AI Investigation Log",
            "question": "Which inventory has not moved for 90 days?",
            "status": "ok",
            "steps": [{"status": "ok"}],  # missing skill_name
        })
        with self.assertRaises(frappe.exceptions.MandatoryError):
            doc.insert(ignore_permissions=True)