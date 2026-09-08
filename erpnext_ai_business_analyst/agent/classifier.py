"""
Question -> starting Skill classification.

Step 8 (MVP_PLAN.md): deterministic keyword matching only — no LLM. Scores
each registered Skill by how many of its `triggers` phrases appear as
substrings in the lowercased question; picks the highest score. This is
intentionally dumb — it exists to validate the planner's hop/chain/conclude
mechanics before paying LLM classification cost. Step 9 replaces this
function's body with an LLM call; callers (planner.py) don't change.
"""

from __future__ import annotations

from erpnext_ai_business_analyst.skills.registry import SkillRegistry


def classify_question(question: str, skill_registry: SkillRegistry) -> str | None:
    q = question.lower()
    best_skill_name: str | None = None
    best_score = 0

    for skill in skill_registry.all():
        score = sum(1 for trigger in skill.triggers if trigger.lower() in q)
        if score > best_score:
            best_score = score
            best_skill_name = skill.name

    return best_skill_name