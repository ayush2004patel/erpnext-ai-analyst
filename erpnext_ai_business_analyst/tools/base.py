"""
Base contract for all Tools.

A Tool is a typed, read-only, permission-aware callable that queries ERPNext.
No side effects. No domain logic here — this file is domain-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

import frappe


class ToolStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"      # e.g. permission denied on part of the query
    ERROR = "error"


@dataclass(frozen=True)
class ToolParam:
    """One parameter a Tool accepts."""
    name: str
    type: str                      # "str" | "int" | "float" | "date" | "list"
    required: bool = True
    description: str = ""
    default: Any = None


@dataclass
class QueryMeta:
    """
    Mandatory provenance for every Tool call — feeds the Evidence layer directly.
    Never optional: build it in at call time, don't reconstruct later.
    """
    doctype: str
    filters: dict
    fields: list[str]
    row_count: int


@dataclass
class ToolResult:
    status: ToolStatus
    data: list[dict] = field(default_factory=list)
    query_meta: Optional[QueryMeta] = None
    error: Optional[str] = None
    denied_reason: Optional[str] = None   # set when status == PARTIAL/ERROR due to permissions


@dataclass
class Tool:
    """
    A registered, callable Tool.

    `func` must:
      - run as the invoking user (frappe.session.user) — never ignore_permissions=True
      - return a ToolResult
      - perform no writes (enforced separately by the no-side-effects lint in tests/)
    """
    name: str                      # unique, e.g. "inventory.get_reorder_status"
    description: str
    params: list[ToolParam]
    func: Callable[..., ToolResult]

    def __call__(self, **kwargs) -> ToolResult:
        self._validate_params(kwargs)
        try:
            result = self.func(**kwargs)
        except frappe.PermissionError as e:
            return ToolResult(status=ToolStatus.ERROR, error=str(e), denied_reason=str(e))
        except Exception as e:  # noqa: BLE001 — tool boundary, must not raise into Skill layer
            frappe.log_error(title=f"Tool failed: {self.name}", message=str(e))
            return ToolResult(status=ToolStatus.ERROR, error=str(e))

        if not isinstance(result, ToolResult):
            raise TypeError(f"Tool '{self.name}' must return a ToolResult, got {type(result)}")
        return result

    def _validate_params(self, kwargs: dict) -> None:
        allowed = {p.name for p in self.params}
        unknown = set(kwargs) - allowed
        if unknown:
            raise ValueError(f"Tool '{self.name}' got unknown params: {unknown}")

        for p in self.params:
            if p.required and p.name not in kwargs and p.default is None:
                raise ValueError(f"Tool '{self.name}' missing required param: {p.name}")