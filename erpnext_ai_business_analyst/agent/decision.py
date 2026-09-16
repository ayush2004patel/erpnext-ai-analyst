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


VALID_CONCLUDE_CATEGORIES = {"conversational", "no_matching_skill"}


@dataclass(frozen=True)
class Decision:
    action: str                                    # "RUN" | "CONCLUDE"
    skill_name: str | None = None
    inputs: dict = field(default_factory=dict)
    category: str | None = None                     # only meaningful for a first-decision
                                                      # CONCLUDE: "conversational" | "no_matching_skill"


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
    is_first_decision: bool,
) -> tuple[str, str]:
    """
    `is_first_decision` is True only for the very first decision of an
    investigation (history empty) — that's the only point where a CONCLUDE
    must also say WHY nothing ran: "conversational" (not a business
    question at all) vs "no_matching_skill" (a real business/ERP question,
    but no candidate Skill covers it). Mid-chain CONCLUDE (after at least
    one Skill has already run and produced real findings) keeps its
    original unqualified meaning — the prompt text for that case is
    unchanged from before this distinction existed.
    """
    if is_first_decision:
        system_prompt = (
            "You are the planning component of an ERPNext AI Business Analyst investigating "
            "a business question step by step. Given the question, what has been found so far, "
            "and a list of candidate skills for the next step, decide what to do next.\n\n"
            "Respond with ONLY a single JSON object — no prose, no markdown code fences, no "
            "explanation. It must match exactly one of these three shapes:\n"
            '{"action": "RUN", "skill_name": "<one of the candidate skill names>", "inputs": {}}\n'
            '{"action": "CONCLUDE", "category": "conversational"}\n'
            '{"action": "CONCLUDE", "category": "no_matching_skill"}\n\n'
            "Choose RUN only when a candidate skill would meaningfully add to answering the "
            "question.\n"
            'Choose CONCLUDE with category "conversational" when the question is not a '
            "business/ERP question at all — greetings, small talk, or an unrelated topic.\n"
            'Choose CONCLUDE with category "no_matching_skill" when the question IS a real '
            "business/ERP question, but none of the candidate skills can answer it."
        )
    else:
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


def parse_decision(raw_text: str, valid_skill_names: set[str], is_first_decision: bool) -> Decision:
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
        if not is_first_decision:
            # Mid-chain CONCLUDE keeps its original unqualified meaning —
            # category isn't requested here and is ignored even if present.
            return Decision(action="CONCLUDE")

        category = data.get("category")
        if category not in VALID_CONCLUDE_CATEGORIES:
            raise InvalidDecisionError(
                f"First-decision CONCLUDE must include a valid category "
                f"(one of {sorted(VALID_CONCLUDE_CATEGORIES)}), got: {category!r}"
            )
        return Decision(action="CONCLUDE", category=category)

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