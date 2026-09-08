"""
Unit tests for agent/decision.py's parse_decision — no Frappe site needed,
these are pure schema-validation checks.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_agent_decision
"""

from __future__ import annotations

import unittest

from erpnext_ai_business_analyst.agent.decision import InvalidDecisionError, parse_decision


class TestParseDecision(unittest.TestCase):
    VALID_SKILLS = {"inventory.dead_stock", "inventory.overstock"}

    def test_valid_run(self):
        decision = parse_decision(
            '{"action": "RUN", "skill_name": "inventory.dead_stock", "inputs": {"warehouse": "W1"}}',
            self.VALID_SKILLS,
        )
        self.assertEqual(decision.action, "RUN")
        self.assertEqual(decision.skill_name, "inventory.dead_stock")
        self.assertEqual(decision.inputs, {"warehouse": "W1"})

    def test_valid_run_without_inputs_defaults_to_empty_dict(self):
        decision = parse_decision(
            '{"action": "RUN", "skill_name": "inventory.dead_stock"}', self.VALID_SKILLS,
        )
        self.assertEqual(decision.inputs, {})

    def test_valid_conclude(self):
        decision = parse_decision('{"action": "CONCLUDE"}', self.VALID_SKILLS)
        self.assertEqual(decision.action, "CONCLUDE")
        self.assertIsNone(decision.skill_name)

    def test_strips_markdown_code_fences(self):
        decision = parse_decision(
            '```json\n{"action": "CONCLUDE"}\n```', self.VALID_SKILLS,
        )
        self.assertEqual(decision.action, "CONCLUDE")

    def test_rejects_malformed_json(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision("not json at all", self.VALID_SKILLS)

    def test_rejects_non_object_json(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision('["RUN", "inventory.dead_stock"]', self.VALID_SKILLS)

    def test_rejects_unknown_action(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision('{"action": "MAYBE"}', self.VALID_SKILLS)

    def test_rejects_missing_action(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision('{"skill_name": "inventory.dead_stock"}', self.VALID_SKILLS)

    def test_rejects_run_with_unknown_skill_name(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision(
                '{"action": "RUN", "skill_name": "inventory.made_up"}', self.VALID_SKILLS,
            )

    def test_rejects_run_with_missing_skill_name(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision('{"action": "RUN"}', self.VALID_SKILLS)

    def test_rejects_non_dict_inputs(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision(
                '{"action": "RUN", "skill_name": "inventory.dead_stock", "inputs": "not a dict"}',
                self.VALID_SKILLS,
            )