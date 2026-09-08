"""
SkillRegistry — discovers and holds all registered Skills.

Skills are declared via the `ai_analyst_skills` hook in any installed app's
hooks.py, same pluggability pattern as ToolRegistry. Validates at load time
that every Skill's declared `tools_used` actually exist in ToolRegistry —
fails fast on a misconfigured Skill instead of failing later mid-investigation.
"""

from __future__ import annotations

import frappe

from erpnext_ai_business_analyst.skills.base import Skill
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


class SkillRegistry:
    _instance: "SkillRegistry | None" = None

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    @classmethod
    def get(cls) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load()
        return cls._instance

    def load(self) -> None:
        self._skills.clear()
        tool_registry = ToolRegistry.get()

        for dotted_path in frappe.get_hooks("ai_analyst_skills"):
            obj = frappe.get_attr(dotted_path)
            skill = obj() if callable(obj) and not isinstance(obj, Skill) else obj
            self._validate_tools_exist(skill, tool_registry)
            self.register(skill)

    def _validate_tools_exist(self, skill: Skill, tool_registry: ToolRegistry) -> None:
        missing = [t for t in skill.tools_used if t not in tool_registry.names()]
        if missing:
            raise ValueError(
                f"Skill '{skill.name}' declares tools_used {missing} "
                f"that are not registered in ToolRegistry"
            )

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"Duplicate skill name: {skill.name}")
        self._skills[skill.name] = skill

    def get_skill(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"Unknown skill: {name}")
        return self._skills[name]

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def names(self) -> list[str]:
        return list(self._skills.keys())