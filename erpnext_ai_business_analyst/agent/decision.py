"""
The planner's RUN/CONCLUDE decision — schema, prompt construction, and
validation of the LLM's response before the planner acts on it.

Context sent to the LLM is findings + confidence only, never raw evidence
records (ARCHITECTURE.md §6) — keeps prompts small and avoids re-sending
full record dumps on every hop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erpnext_ai_business_analyst.agent.planner import InvestigationStep
    from erpnext_ai_business_analyst.skills.base import Skill


class InvalidDecisionError(Exception):
    """Raised when the LLM's response doesn't match the required schema.
    The planner catches this and fails safe (concludes early) rather than
    acting on an unvalidated response."""


@dataclass(frozen=True)
class Decision:
    action: str                                    # "RUN" | "CONCLUDE"
    skill_name: str | None = None
    inputs: dict = field(default_factory=dict)


def _summarize_history(history: "list[InvestigationStep]") -> str:
    if not history:
        return "(no skills run yet)"

    lines = []
    for step in history:
        lines.append(f"- Ran {step.skill_name} (status: {step.result.status})")
        for finding in step.result.findings:
            lines.append(f"    finding (confidence {finding.confidence}): {finding.claim}")
        if step.result.metrics:
            lines.append(f"    metrics: {step.result.metrics}")
    return "\n".join(lines)


def build_decision_prompt(
    question: str,
    history: "list[InvestigationStep]",
    candidate_skills: "list[Skill]",
) -> tuple[str, str]:
    system_prompt = (
        "You are the planning component of an ERPNext AI Business Analyst investigating "
        "a business question step by step. Given the question, what has been found so far, "
        "and a list of candidate skills for the next step, decide what to do next.\n\n"
        "Respond with ONLY a single JSON object — no prose, no markdown code fences, no "
        "explanation. It must match exactly one of these two shapes:\n"
        '{"action": "RUN", "skill_name": "<one of the candidate skill names>", "inputs": {}}\n'
        '{"action": "CONCLUDE"}\n\n'
        "Choose RUN only when a candidate skill would meaningfully add to answering the "
        "question. Choose CONCLUDE once you have enough findings, or if no candidate skill "
        "is relevant."
    )

    candidates_desc = "\n".join(
        f"- {s.name}: {s.description} (triggers: {', '.join(s.triggers)})"
        for s in candidate_skills
    ) or "(no candidate skills available)"

    user_prompt = (
        f"Question: {question}\n\n"
        f"Investigation so far:\n{_summarize_history(history)}\n\n"
        f"Candidate skills for the next step:\n{candidates_desc}\n\n"
        "Decide the next step."
    )
    return system_prompt, user_prompt


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text[3:]
        if text.lower().startswith("json"):
            text = text[4:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def parse_decision(raw_text: str, valid_skill_names: set[str]) -> Decision:
    text = _strip_code_fences(raw_text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise InvalidDecisionError(f"LLM response was not valid JSON: {e}") from e

    if not isinstance(data, dict):
        raise InvalidDecisionError(f"LLM response JSON must be an object, got {type(data)}")

    action = data.get("action")
    if action not in ("RUN", "CONCLUDE"):
        raise InvalidDecisionError(f"Unknown or missing action: {action!r}")

    if action == "CONCLUDE":
        return Decision(action="CONCLUDE")

    skill_name = data.get("skill_name")
    if not isinstance(skill_name, str) or skill_name not in valid_skill_names:
        raise InvalidDecisionError(
            f"RUN action referenced an invalid/unknown skill_name: {skill_name!r} "
            f"(valid: {sorted(valid_skill_names)})"
        )

    inputs = data.get("inputs", {})
    if not isinstance(inputs, dict):
        raise InvalidDecisionError(f"'inputs' must be an object, got {type(inputs)}")

    return Decision(action="RUN", skill_name=skill_name, inputs=inputs)