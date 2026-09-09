"""
Tests for agent/persistence.py and agent/service.py.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_agent_persistence
"""

from __future__ import annotations

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_ai_business_analyst.agent.persistence import save_investigation_log
from erpnext_ai_business_analyst.agent.planner import InvestigationResult, InvestigationStep
from erpnext_ai_business_analyst.agent.service import investigate
from erpnext_ai_business_analyst.skills.base import (
    Evidence,
    Finding,
    SkillResult,
    SkillStatus,
)
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


def _make_dead_and_overstocked_item(suffix: str) -> str:
    company = get_or_create_company()
    warehouse = create_warehouse(company, suffix)
    item_code = create_item(suffix, reorder_rows=[{
        "warehouse": warehouse, "warehouse_reorder_level": 50, "warehouse_reorder_qty": 10,
    }])
    create_bin(item_code, warehouse, actual_qty=310)
    insert_sle(item_code, warehouse, qty_after_transaction=310,
               actual_qty=310, days_ago=200, voucher_no=f"AI-TEST-{suffix}")
    return warehouse


class TestSaveInvestigationLog(FrappeTestCase):
    def test_saves_log_with_step_and_evidence_data(self):
        fake_result = InvestigationResult(
            status="ok",
            hop_count=1,
            metrics={"inventory.dead_stock": {"dead_item_count": 1}},
            evidence=[],       # merged/top-level evidence isn't persisted separately — see docstring note
            findings=[],
            decision_errors=[],
            history=[
                InvestigationStep(
                    skill_name="inventory.dead_stock",
                    inputs={"warehouse": "W1"},
                    result=SkillResult(
                        status=SkillStatus.OK,
                        findings=[Finding(
                            claim="Item X is dead stock", confidence=0.9,
                            supporting_evidence_ids=["ev-movement"],
                        )],
                        metrics={"dead_item_count": 1},
                        evidence=[Evidence(
                            id="ev-movement", source_tool="inventory.get_item_movement",
                            query_meta={"doctype": "Bin", "row_count": 1},
                            records=[{"item_code": "X"}], summary="1 item",
                        )],
                    ),
                ),
            ],
        )

        log_name = save_investigation_log("Which inventory has not moved for 90 days?", fake_result)
        doc = frappe.get_doc("AI Investigation Log", log_name)

        self.assertEqual(doc.question, "Which inventory has not moved for 90 days?")
        self.assertEqual(doc.status, "ok")
        self.assertEqual(doc.hop_count, 1)
        self.assertEqual(
            json.loads(doc.metrics), {"inventory.dead_stock": {"dead_item_count": 1}}
        )
        self.assertEqual(json.loads(doc.decision_errors), [])

        self.assertEqual(len(doc.steps), 1)
        step = doc.steps[0]
        self.assertEqual(step.skill_name, "inventory.dead_stock")
        self.assertEqual(step.status, "ok")
        self.assertEqual(json.loads(step.inputs), {"warehouse": "W1"})

        findings = json.loads(step.findings)
        self.assertEqual(findings[0]["claim"], "Item X is dead stock")
        self.assertAlmostEqual(findings[0]["confidence"], 0.9)

        evidence = json.loads(step.evidence)
        self.assertEqual(evidence[0]["source_tool"], "inventory.get_item_movement")
        self.assertEqual(evidence[0]["query_meta"], {"doctype": "Bin", "row_count": 1})

    def test_saves_log_with_no_steps(self):
        fake_result = InvestigationResult(status="no_skill_matched", hop_count=0)
        log_name = save_investigation_log("What's the weather today?", fake_result)
        doc = frappe.get_doc("AI Investigation Log", log_name)

        self.assertEqual(doc.status, "no_skill_matched")
        self.assertEqual(len(doc.steps), 0)


class TestInvestigateServiceEndToEnd(FrappeTestCase):
    def test_runs_and_persists_a_real_chained_investigation(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = _make_dead_and_overstocked_item(suffix)

        llm = ScriptedLLMClient([RUN_DEAD_STOCK, RUN_OVERSTOCK, RUN_SLOW_MOVING])
        result, log_name = investigate(
            question="Which inventory has not moved for 90 days?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
            initial_inputs={"warehouse": warehouse},
            max_hops=4,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.history), 3)

        doc = frappe.get_doc("AI Investigation Log", log_name)
        self.assertEqual(doc.question, "Which inventory has not moved for 90 days?")
        self.assertEqual(doc.status, "ok")
        self.assertEqual(doc.hop_count, 3)
        self.assertEqual(len(doc.steps), 3)
        self.assertEqual(
            [s.skill_name for s in doc.steps],
            ["inventory.dead_stock", "inventory.overstock", "inventory.slow_moving_stock"],
        )
        # Third step (slow_moving_stock) found nothing for this item -> no_data, empty findings.
        self.assertEqual(doc.steps[2].status, "no_data")
        self.assertEqual(json.loads(doc.steps[2].findings), [])