"""
ToolRegistry — discovers and holds all registered Tools.

Tools are declared via the `ai_analyst_tools` hook in any installed app's
hooks.py, as a list of dotted paths to Tool instances or zero-arg factory
functions returning a Tool. This is what makes Tools pluggable across apps
without forking this one.
"""

from __future__ import annotations

import frappe

from erpnext_ai_business_analyst.tools.base import Tool

class ToolRegistry:
    _instance: "ToolRegistry | None" = None

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._loaded = False

    @classmethod
    def get(cls) -> "ToolRegistry":
        """Singleton, load-once-on-boot. Call load() explicitly to force a reload
        (e.g. from bench console during dev — no hot-reload in request handling)."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load()
        return cls._instance

    def load(self) -> None:
        self._tools.clear()
        for dotted_path in frappe.get_hooks("ai_analyst_tools"):
            obj = frappe.get_attr(dotted_path)
            tool = obj() if callable(obj) and not isinstance(obj, Tool) else obj
            self.register(tool)
        self._loaded = True

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())