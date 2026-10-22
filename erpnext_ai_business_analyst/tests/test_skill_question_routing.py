"""Regression tests ensuring every configured inventory Skill is reachable."""

from importlib import import_module
from unittest import TestCase

from erpnext_ai_business_analyst.agent.classifier import classify_question
from erpnext_ai_business_analyst.hooks import ai_analyst_skills


class _SkillRegistryStub:
    def __init__(self, skills):
        self._skills = skills

    def all(self):
        return self._skills


def _load_configured_skills():
    skills = []
    for dotted_path in ai_analyst_skills:
        module_path, attribute = dotted_path.rsplit(".", 1)
        skills.append(getattr(import_module(module_path), attribute))
    return skills


class TestSkillQuestionRouting(TestCase):
    def test_every_configured_skill_has_a_unique_routable_trigger(self):
        skills = _load_configured_skills()
        registry = _SkillRegistryStub(skills)
        unreachable = []

        for skill in skills:
            # The longest phrases are the most specific examples a user can ask.
            questions = sorted(skill.triggers, key=len, reverse=True)
            if not any(classify_question(question, registry) == skill.name for question in questions):
                unreachable.append(skill.name)

        self.assertEqual(unreachable, [], f"Skills without a unique question trigger: {unreachable}")
