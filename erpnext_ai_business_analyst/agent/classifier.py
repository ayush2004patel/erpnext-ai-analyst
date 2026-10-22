"""
Question -> starting Skill classification.

Uses deterministic phrase matching only. The most specific matching phrase
wins, so a question such as "missing reorder level" reaches the configuration
Skill instead of the broader "reorder" Skill. Callers remain provider-agnostic.
"""

from __future__ import annotations

from erpnext_ai_business_analyst.skills.registry import SkillRegistry


def classify_question(question: str, skill_registry: SkillRegistry) -> str | None:
    q = question.lower()
    best_skill_name: str | None = None
    best_score = 0

    for skill in skill_registry.all():
        # Phrase word-count is a simple, explainable specificity score.
        # Do not add all matches: broad Skills often contain short words that
        # would otherwise overpower one precise phrase in another Skill.
        score = max(
            (len(trigger.split()) for trigger in skill.triggers if trigger.lower() in q),
            default=0,
        )
        if score > best_score:
            best_score = score
            best_skill_name = skill.name

    return best_skill_name
