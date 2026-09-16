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


class TestParseDecisionRun(unittest.TestCase):
    """RUN validation is identical regardless of is_first_decision."""

    VALID_SKILLS = {"inventory.dead_stock", "inventory.overstock"}

    def test_valid_run(self):
        decision = parse_decision(
            '{"action": "RUN", "skill_name": "inventory.dead_stock", "inputs": {"warehouse": "W1"}}',
            self.VALID_SKILLS, is_first_decision=True,
        )
        self.assertEqual(decision.action, "RUN")
        self.assertEqual(decision.skill_name, "inventory.dead_stock")
        self.assertEqual(decision.inputs, {"warehouse": "W1"})
        self.assertIsNone(decision.category)

    def test_valid_run_without_inputs_defaults_to_empty_dict(self):
        decision = parse_decision(
            '{"action": "RUN", "skill_name": "inventory.dead_stock"}',
            self.VALID_SKILLS, is_first_decision=True,
        )
        self.assertEqual(decision.inputs, {})

    def test_strips_markdown_code_fences(self):
        decision = parse_decision(
            '```json\n{"action": "RUN", "skill_name": "inventory.dead_stock"}\n```',
            self.VALID_SKILLS, is_first_decision=True,
        )
        self.assertEqual(decision.action, "RUN")

    def test_rejects_malformed_json(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision("not json at all", self.VALID_SKILLS, is_first_decision=True)

    def test_rejects_non_object_json(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision('["RUN", "inventory.dead_stock"]', self.VALID_SKILLS, is_first_decision=True)

    def test_rejects_unknown_action(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision('{"action": "MAYBE"}', self.VALID_SKILLS, is_first_decision=True)

    def test_rejects_missing_action(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision(
                '{"skill_name": "inventory.dead_stock"}', self.VALID_SKILLS, is_first_decision=True,
            )

    def test_rejects_run_with_unknown_skill_name(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision(
                '{"action": "RUN", "skill_name": "inventory.made_up"}',
                self.VALID_SKILLS, is_first_decision=True,
            )

    def test_rejects_run_with_missing_skill_name(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision('{"action": "RUN"}', self.VALID_SKILLS, is_first_decision=True)

    def test_rejects_non_dict_inputs(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision(
                '{"action": "RUN", "skill_name": "inventory.dead_stock", "inputs": "not a dict"}',
                self.VALID_SKILLS, is_first_decision=True,
            )


class TestParseDecisionConcludeFirstDecision(unittest.TestCase):
    """First-decision CONCLUDE (history empty) requires a valid category."""

    VALID_SKILLS = {"inventory.dead_stock", "inventory.overstock"}

    def test_valid_conversational(self):
        decision = parse_decision(
            '{"action": "CONCLUDE", "category": "conversational"}',
            self.VALID_SKILLS, is_first_decision=True,
        )
        self.assertEqual(decision.action, "CONCLUDE")
        self.assertEqual(decision.category, "conversational")

    def test_valid_no_matching_skill(self):
        decision = parse_decision(
            '{"action": "CONCLUDE", "category": "no_matching_skill"}',
            self.VALID_SKILLS, is_first_decision=True,
        )
        self.assertEqual(decision.category, "no_matching_skill")

    def test_rejects_missing_category(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision('{"action": "CONCLUDE"}', self.VALID_SKILLS, is_first_decision=True)

    def test_rejects_invalid_category_value(self):
        with self.assertRaises(InvalidDecisionError):
            parse_decision(
                '{"action": "CONCLUDE", "category": "not_a_real_category"}',
                self.VALID_SKILLS, is_first_decision=True,
            )


class TestParseDecisionConcludeMidChain(unittest.TestCase):
    """Mid-chain CONCLUDE (history non-empty) keeps its original unqualified
    meaning — no category required, and any category present is ignored."""

    VALID_SKILLS = {"inventory.dead_stock", "inventory.overstock"}

    def test_valid_without_category(self):
        decision = parse_decision('{"action": "CONCLUDE"}', self.VALID_SKILLS, is_first_decision=False)
        self.assertEqual(decision.action, "CONCLUDE")
        self.assertIsNone(decision.category)

    def test_category_present_is_ignored(self):
        decision = parse_decision(
            '{"action": "CONCLUDE", "category": "conversational"}',
            self.VALID_SKILLS, is_first_decision=False,
        )
        self.assertEqual(decision.action, "CONCLUDE")
        self.assertIsNone(decision.category)  # ignored, not stored