"""
Tests for agent/planner.py, using ScriptedLLMClient so the real decision/
validation path (agent/decision.py) runs without real API calls.

Uses the same "dead stock + overstocked" fixture item as the Step 8 tests
so the real suggested_next_skills chain (dead_stock -> overstock ->
slow_moving_stock) exercises for real.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_agent_planner
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_ai_business_analyst.agent.planner import run_investigation
from erpnext_ai_business_analyst.skills.registry import SkillRegistry
from erpnext_ai_business_analyst.tools.registry import ToolRegistry
from erpnext_ai_business_analyst.tests.fixtures import (
    create_bin,
    create_item,
    create_warehouse,
    get_or_create_company,
    insert_sle,
)
from erpnext_ai_business_analyst.tests.llm_fakes import ScriptedLLMClient

RUN_DEAD_STOCK = '{"action": "RUN", "skill_name": "inventory.dead_stock", "inputs": {}}'
RUN_OVERSTOCK = '{"action": "RUN", "skill_name": "inventory.overstock", "inputs": {}}'
RUN_SLOW_MOVING = '{"action": "RUN", "skill_name": "inventory.slow_moving_stock", "inputs": {}}'
CONCLUDE = '{"action": "CONCLUDE"}'


def _make_dead_and_overstocked_item(suffix: str) -> str:
    """ROL=50, stock=310 (ratio 6.2 -> overstock severe) and last movement
    200 days ago with no consumption in the window (-> dead stock long-dead,
    and excluded from slow_moving_stock since qty_out_in_window == 0)."""
    company = get_or_create_company()
    warehouse = create_warehouse(company, suffix)
    item_code = create_item(suffix, reorder_rows=[{
        "warehouse": warehouse, "warehouse_reorder_level": 50, "warehouse_reorder_qty": 10,
    }])
    create_bin(item_code, warehouse, actual_qty=310)
    insert_sle(item_code, warehouse, qty_after_transaction=310,
               actual_qty=310, days_ago=200, voucher_no=f"AI-TEST-{suffix}")
    return warehouse


class TestRunInvestigation(FrappeTestCase):
    def test_chains_via_llm_decisions_and_concludes_naturally(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = _make_dead_and_overstocked_item(suffix)

        llm = ScriptedLLMClient([RUN_DEAD_STOCK, RUN_OVERSTOCK, RUN_SLOW_MOVING])
        result = run_investigation(
            question="Which inventory has not moved for 90 days?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
            initial_inputs={"warehouse": warehouse},
            max_hops=4,
        )

        self.assertEqual(result.status, "ok")  # concluded naturally, not truncated
        self.assertEqual(
            [s.skill_name for s in result.history],
            ["inventory.dead_stock", "inventory.overstock", "inventory.slow_moving_stock"],
        )
        self.assertEqual(result.decision_errors, [])
        # Loop stopped calling the LLM once slow_moving_stock had no further
        # suggestions — no 4th scripted response was needed.
        self.assertEqual(len(llm.calls), 3)
        self.assertTrue(any(f.claim.startswith("[inventory.dead_stock]") for f in result.findings))
        self.assertTrue(any(f.claim.startswith("[inventory.overstock]") for f in result.findings))

    def test_truncates_when_max_hops_reached_mid_chain(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = _make_dead_and_overstocked_item(suffix)

        llm = ScriptedLLMClient([RUN_DEAD_STOCK, RUN_OVERSTOCK])
        result = run_investigation(
            question="Which inventory has not moved for 90 days?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
            initial_inputs={"warehouse": warehouse},
            max_hops=2,
        )

        self.assertEqual(result.status, "truncated")
        self.assertEqual(
            [s.skill_name for s in result.history],
            ["inventory.dead_stock", "inventory.overstock"],
        )

    def test_llm_concludes_immediately(self):
        llm = ScriptedLLMClient([CONCLUDE])
        result = run_investigation(
            question="What's the weather today?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.history, [])
        self.assertEqual(result.decision_errors, [])

    def test_fails_safe_on_malformed_llm_response(self):
        llm = ScriptedLLMClient(["not valid json at all"])
        result = run_investigation(
            question="Which inventory has not moved for 90 days?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.history, [])
        self.assertEqual(len(result.decision_errors), 1)
        self.assertIn("not valid JSON", result.decision_errors[0])

    def test_fails_safe_on_unknown_skill_name(self):
        llm = ScriptedLLMClient(['{"action": "RUN", "skill_name": "inventory.made_up_skill"}'])
        result = run_investigation(
            question="Which inventory has not moved for 90 days?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.history, [])
        self.assertEqual(len(result.decision_errors), 1)
        self.assertIn("invalid/unknown skill_name", result.decision_errors[0])

    def test_evidence_ids_are_namespaced_per_skill(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = _make_dead_and_overstocked_item(suffix)

        llm = ScriptedLLMClient([RUN_DEAD_STOCK, RUN_OVERSTOCK, RUN_SLOW_MOVING])
        result = run_investigation(
            question="Which inventory has not moved for 90 days?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
            initial_inputs={"warehouse": warehouse},
            max_hops=4,
        )

        evidence_ids = [e.id for e in result.evidence]
        self.assertEqual(len(evidence_ids), len(set(evidence_ids)))  # no collisions
        self.assertTrue(any(eid.startswith("inventory.dead_stock#") for eid in evidence_ids))
        self.assertTrue(any(eid.startswith("inventory.overstock#") for eid in evidence_ids))