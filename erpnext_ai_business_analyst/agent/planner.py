"""
Investigation Agent / Planner.

Step 9: the classifier and the "follow the first suggestion" rule from
Step 8 are replaced by a single LLM decision point (see agent/decision.py)
— used BOTH to pick the starting Skill (hop 0, candidates = full registry)
AND to decide RUN-vs-CONCLUDE on every subsequent hop (candidates = the
previous Skill's suggested_next_skills). The loop shape, state, and
evidence-merging (_merge_history) are unchanged from Step 8.

No Anthropic-specific code here — only the LLMClient interface. Anthropic
is one implementation (agent/llm/anthropic_client.py); a fake is used in
tests (tests/llm_fakes.py) to keep the loop deterministically testable
without real API calls.

Fail-safe: an invalid/unparseable LLM response never gets executed. It's
recorded in InvestigationResult.decision_errors and the investigation
concludes early with whatever history it already has, rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from erpnext_ai_business_analyst.agent.decision import (
    Decision,
    InvalidDecisionError,
    build_decision_prompt,
    parse_decision,
)
from erpnext_ai_business_analyst.agent.llm.base import LLMClient
from erpnext_ai_business_analyst.skills.base import Evidence, Finding, NextSkillSuggestion, SkillResult
from erpnext_ai_business_analyst.skills.registry import SkillRegistry
from erpnext_ai_business_analyst.tools.registry import ToolRegistry

DEFAULT_MAX_HOPS = 4


@dataclass
class InvestigationStep:
    skill_name: str
    inputs: dict
    result: SkillResult


@dataclass
class InvestigationResult:
    status: str                                    # "ok" | "truncated"
    findings: list[Finding] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)     # keyed by skill_name
    evidence: list[Evidence] = field(default_factory=list)
    history: list[InvestigationStep] = field(default_factory=list)
    hop_count: int = 0
    decision_errors: list[str] = field(default_factory=list)  # non-empty if the LLM ever
                                                                 # returned an invalid decision


def _filter_to_allowed_params(inputs: dict, allowed_param_names: set[str]) -> dict:
    """Different Skills declare different param sets. Never pass a param the
    target Skill doesn't accept — Skill.run rejects unknown kwargs by design."""
    return {k: v for k, v in inputs.items() if k in allowed_param_names}


def _merge_history(
    history: list[InvestigationStep], truncated: bool, decision_errors: list[str] | None = None
) -> InvestigationResult:
    all_findings: list[Finding] = []
    all_evidence: list[Evidence] = []
    metrics_by_skill: dict = {}

    for step in history:
        result = step.result
        prefix = f"{step.skill_name}#"
        id_map: dict[str, str] = {}

        for ev in result.evidence:
            new_id = prefix + ev.id
            id_map[ev.id] = new_id
            all_evidence.append(Evidence(
                id=new_id, source_tool=ev.source_tool,
                query_meta=ev.query_meta, records=ev.records, summary=ev.summary,
            ))

        for finding in result.findings:
            namespaced_ids = [id_map.get(eid, eid) for eid in finding.supporting_evidence_ids]
            all_findings.append(Finding(
                claim=f"[{step.skill_name}] {finding.claim}",
                confidence=finding.confidence,
                supporting_evidence_ids=namespaced_ids,
            ))

        metrics_by_skill[step.skill_name] = result.metrics

    all_findings.sort(key=lambda f: f.confidence, reverse=True)

    return InvestigationResult(
        status="truncated" if truncated else "ok",
        findings=all_findings,
        metrics=metrics_by_skill,
        evidence=all_evidence,
        history=history,
        hop_count=len(history),
        decision_errors=decision_errors or [],
    )


def run_investigation(
    question: str,
    tool_registry: ToolRegistry,
    skill_registry: SkillRegistry,
    llm_client: LLMClient,
    initial_inputs: dict | None = None,
    max_hops: int = DEFAULT_MAX_HOPS,
) -> InvestigationResult:
    initial_inputs = initial_inputs or {}
    history: list[InvestigationStep] = []
    visited: set[str] = set()
    decision_errors: list[str] = []

    # Hop 0: candidates = the full registry (this is the "classifier" role).
    # Subsequent hops: candidates = the previous result's suggested_next_skills.
    candidates = skill_registry.all()
    suggestion_by_name: dict[str, NextSkillSuggestion] = {}
    current_inputs = dict(initial_inputs)

    while len(history) < max_hops:
        available = [s for s in candidates if s.name not in visited]
        if not available:
            return _merge_history(history, truncated=False, decision_errors=decision_errors)

        system_prompt, user_prompt = build_decision_prompt(question, history, available)
        valid_names = {s.name for s in available}

        try:
            raw = llm_client.complete(system_prompt, user_prompt)
            decision: Decision = parse_decision(raw, valid_names)
        except InvalidDecisionError as e:
            decision_errors.append(str(e))
            return _merge_history(history, truncated=False, decision_errors=decision_errors)

        if decision.action == "CONCLUDE":
            return _merge_history(history, truncated=False, decision_errors=decision_errors)

        skill = skill_registry.get_skill(decision.skill_name)
        suggestion = suggestion_by_name.get(decision.skill_name)
        suggestion_inputs = suggestion.inputs_to_pass if suggestion else {}
        # Priority: LLM-provided inputs > chained suggestion's inputs > carried-over inputs.
        merged_inputs = {**current_inputs, **suggestion_inputs, **decision.inputs}
        call_inputs = _filter_to_allowed_params(merged_inputs, {p.name for p in skill.params})

        result = skill.run(tool_registry, **call_inputs)
        history.append(InvestigationStep(
            skill_name=decision.skill_name, inputs=dict(call_inputs), result=result
        ))
        visited.add(decision.skill_name)
        current_inputs = call_inputs

        suggestion_by_name = {
            s.skill_name: s for s in result.suggested_next_skills
            if s.skill_name in skill_registry.names() and s.skill_name not in visited
        }
        candidates = [skill_registry.get_skill(name) for name in suggestion_by_name]

    has_more = bool(candidates)
    return _merge_history(history, truncated=has_more, decision_errors=decision_errors)