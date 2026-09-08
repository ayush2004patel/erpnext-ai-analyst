"""
Base contract for all Skills.

A Skill wraps one or more Tools to produce structured findings + evidence,
not prose. Mirrors tools/base.py's Tool pattern: a dataclass holding a
callable, validated and invoked uniformly. No domain logic here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

import frappe

if TYPE_CHECKING:
    from erpnext_ai_business_analyst.tools.registry import ToolRegistry


class SkillStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    NO_DATA = "no_data"
    ERROR = "error"


@dataclass(frozen=True)
class SkillParam:
    name: str
    type: str
    required: bool = True
    description: str = ""
    default: Any = None


@dataclass
class Finding:
    claim: str
    confidence: float                                  # 0.0–1.0
    supporting_evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Evidence:
    id: str
    source_tool: str
    query_meta: dict                                    # dict form of the Tool's QueryMeta
    records: list[dict]
    summary: str


@dataclass
class NextSkillSuggestion:
    skill_name: str
    reason: str
    inputs_to_pass: dict = field(default_factory=dict)


@dataclass
class SkillResult:
    status: SkillStatus
    findings: list[Finding] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    suggested_next_skills: list[NextSkillSuggestion] = field(default_factory=list)
    error: str | None = None


@dataclass
class Skill:
    """
    `func` must:
      - accept `tool_registry` plus the Skill's declared params
      - call Tools via tool_registry.get_tool(name)(**kwargs) — never query
        ERPNext directly
      - return a SkillResult
      - perform no writes (covered by the same no-side-effects lint pattern
        used for tools/, applied to skills/ separately)
    """
    name: str                                            # unique, e.g. "inventory.reorder_demand"
    description: str
    triggers: list[str]                                  # example phrasings/keywords for planner routing
    params: list[SkillParam]
    tools_used: list[str]                                # declared Tool names, validated at registry load
    func: Callable[..., SkillResult]

    def run(self, tool_registry: "ToolRegistry", **kwargs) -> SkillResult:
        self._validate_params(kwargs)
        try:
            result = self.func(tool_registry=tool_registry, **kwargs)
        except Exception as e:  # noqa: BLE001 — skill boundary, must not raise into the planner
            frappe.log_error(title=f"Skill failed: {self.name}", message=str(e))
            return SkillResult(status=SkillStatus.ERROR, error=str(e))

        if not isinstance(result, SkillResult):
            raise TypeError(f"Skill '{self.name}' must return a SkillResult, got {type(result)}")
        return result

    def _validate_params(self, kwargs: dict) -> None:
        allowed = {p.name for p in self.params}
        unknown = set(kwargs) - allowed
        if unknown:
            raise ValueError(f"Skill '{self.name}' got unknown params: {unknown}")

        for p in self.params:
            if p.required and p.name not in kwargs and p.default is None:
                raise ValueError(f"Skill '{self.name}' missing required param: {p.name}")