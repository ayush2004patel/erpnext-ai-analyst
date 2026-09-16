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
from erpnext_ai_business_analyst.tests.llm_fakes import FakeEmbeddingClient, ScriptedLLMClient

RUN_DEAD_STOCK = '{"action": "RUN", "skill_name": "inventory.dead_stock", "inputs": {}}'
RUN_OVERSTOCK = '{"action": "RUN", "skill_name": "inventory.overstock", "inputs": {}}'
RUN_SLOW_MOVING = '{"action": "RUN", "skill_name": "inventory.slow_moving_stock", "inputs": {}}'
CONCLUDE_CONVERSATIONAL = '{"action": "CONCLUDE", "category": "conversational"}'
CONCLUDE_MID_CHAIN = '{"action": "CONCLUDE"}'  # valid only when history is non-empty


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

    def test_llm_concludes_immediately_with_conversational_category(self):
        llm = ScriptedLLMClient([CONCLUDE_CONVERSATIONAL])
        result = run_investigation(
            question="What's the weather today?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.history, [])
        self.assertEqual(result.decision_errors, [])
        self.assertEqual(result.category, "conversational")

    def test_mid_chain_conclude_without_category_still_works(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = _make_dead_and_overstocked_item(suffix)

        # dead_stock runs and finds something, offering inventory.overstock
        # as a next candidate; the model then CONCLUDEs without a category —
        # valid here since history is non-empty (mid-chain), unlike hop 0.
        llm = ScriptedLLMClient([RUN_DEAD_STOCK, CONCLUDE_MID_CHAIN])
        result = run_investigation(
            question="Which inventory has not moved for 90 days?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
            initial_inputs={"warehouse": warehouse},
            max_hops=4,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual([s.skill_name for s in result.history], ["inventory.dead_stock"])
        self.assertEqual(result.decision_errors, [])
        # Mid-chain conclude never sets category, even though a Skill ran.
        self.assertIsNone(result.category)

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
        self.assertIsNone(result.category)

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
        self.assertIsNone(result.category)

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


class TestSemanticRetrievalCandidateSelection(FrappeTestCase):
    """Root Cause B fix: hop-0 candidates narrow to the top_k most
    semantically similar Skills when embedding_client is supplied. Omitting
    it must reproduce today's full-registry behavior exactly — that's the
    backward-compatibility guarantee every other test in this file relies on
    implicitly (none of them pass embedding_client)."""

    def _build_embedding_client_favoring(self, question: str, favored_skill_name: str) -> FakeEmbeddingClient:
        """One-hot vectors per skill (in registry order) — the question's
        vector is identical to the favored skill's (similarity 1.0) and
        orthogonal to every other skill's (similarity 0.0), so top_k
        narrowing is deterministic regardless of registry ordering."""
        all_skills = SkillRegistry.get().all()
        n = len(all_skills)
        vectors: dict[str, list[float]] = {}

        for i, skill in enumerate(all_skills):
            vec = [0.0] * n
            vec[i] = 1.0
            skill_text = f"{skill.description} {' '.join(skill.triggers)}"
            vectors[skill_text] = vec

        favored_index = next(i for i, s in enumerate(all_skills) if s.name == favored_skill_name)
        question_vec = [0.0] * n
        question_vec[favored_index] = 1.0
        vectors[question] = question_vec

        return FakeEmbeddingClient(vectors)

    def test_narrows_candidates_to_top_k_when_embedding_client_supplied(self):
        question = "Which inventory has not moved for 90 days?"
        embedding_client = self._build_embedding_client_favoring(question, "inventory.dead_stock")

        # Fresh, empty warehouse — dead_stock must genuinely find nothing here,
        # regardless of any leftover items from unrelated manual testing
        # elsewhere on the site, so only one LLM decision is ever needed.
        suffix = frappe.generate_hash(length=6)
        warehouse = create_warehouse(get_or_create_company(), suffix)

        llm = ScriptedLLMClient([RUN_DEAD_STOCK])
        result = run_investigation(
            question=question,
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
            initial_inputs={"warehouse": warehouse},
            embedding_client=embedding_client,
            top_k=1,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual([s.skill_name for s in result.history], ["inventory.dead_stock"])

        # The hop-0 prompt should list only the favored candidate, not the
        # other 5 real Skills — proving retrieval actually narrowed the list
        # rather than the LLM happening to pick the right one from all 6.
        _, user_prompt = llm.calls[0]
        self.assertIn("inventory.dead_stock", user_prompt)
        self.assertNotIn("inventory.overstock", user_prompt)
        self.assertNotIn("inventory.stockout_risk", user_prompt)

    def test_omitting_embedding_client_still_offers_the_full_registry(self):
        suffix = frappe.generate_hash(length=6)
        warehouse = create_warehouse(get_or_create_company(), suffix)

        llm = ScriptedLLMClient([RUN_DEAD_STOCK])
        run_investigation(
            question="Which inventory has not moved for 90 days?",
            tool_registry=ToolRegistry.get(),
            skill_registry=SkillRegistry.get(),
            llm_client=llm,
            initial_inputs={"warehouse": warehouse},
            # embedding_client intentionally omitted — today's behavior.
        )

        _, user_prompt = llm.calls[0]
        all_skill_names = [s.name for s in SkillRegistry.get().all()]
        for name in all_skill_names:
            self.assertIn(name, user_prompt)