"""
Persists a completed InvestigationResult into AI Investigation Log / AI
Investigation Step.

Kept separate from planner.py deliberately — the planner stays a pure
decision loop with no DB writes (same separation-of-concerns as Tools
never writing and Skills never querying ERPNext directly). Persistence is
an explicit step the caller opts into (see agent/service.py for the
composed entry point).

Frappe's JSON fieldtype auto-encodes a dict on write but rejects a raw
list ("cannot be a list") — list-shaped values must be pre-encoded with
frappe.as_json() before assignment; dict-shaped values can be passed
natively. (Learned the hard way in Step 10's tests.)

SkillStatus and the investigation's own status are plain str-compatible
values (SkillStatus mixes in `str`), so no explicit .value extraction is
needed before storing them in a Data/Select field.

Note: only each step's own (unprefixed) findings/evidence are persisted,
not InvestigationResult's top-level merged/namespaced findings/evidence —
those are just the same data with skill-name prefixes/namespacing for
in-memory display, so persisting per-step avoids storing everything twice.
"""

from __future__ import annotations

from dataclasses import asdict

import frappe

from erpnext_ai_business_analyst.agent.planner import InvestigationResult


def save_investigation_log(question: str, result: InvestigationResult) -> str:
    """Creates an AI Investigation Log doc (with its AI Investigation Step
    child rows) from a completed InvestigationResult. Returns the new doc's name."""
    log = frappe.get_doc({
        "doctype": "AI Investigation Log",
        "question": question,
        "status": result.status,
        "hop_count": result.hop_count,
        "metrics": result.metrics,                                   # dict -> auto-encoded
        "decision_errors": frappe.as_json(result.decision_errors),   # list -> must pre-encode
        "steps": [
            {
                "skill_name": step.skill_name,
                "status": step.result.status,
                "inputs": step.inputs,                                # dict -> auto-encoded
                "findings": frappe.as_json([asdict(f) for f in step.result.findings]),
                "metrics": step.result.metrics,                       # dict -> auto-encoded
                "evidence": frappe.as_json([asdict(e) for e in step.result.evidence]),
            }
            for step in result.history
        ],
    })
    log.insert(ignore_permissions=True)
    return log.name