"""
Semantic Skill retrieval — ranks Skills by embedding similarity to the
question, instead of the LLM reading trigger-phrase text cold. Only
affects hop-0 candidate selection in planner.py; mid-chain candidates
(from a Skill's suggested_next_skills) are untouched — that chaining
logic already has real prior findings to reason from, so it doesn't have
the same "cold classification over 6+ options" problem this solves.

Skill embeddings are cached in-process per skill name — descriptions and
triggers are static for the process lifetime, so there's no need to
re-embed them on every question.
"""

from __future__ import annotations

import math

from erpnext_ai_business_analyst.agent.llm.embedding_client import EmbeddingClient
from erpnext_ai_business_analyst.skills.base import Skill

_skill_embedding_cache: dict[str, list[float]] = {}


def _skill_text(skill: Skill) -> str:
    return f"{skill.description} {' '.join(skill.triggers)}"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_skill_embedding(skill: Skill, embedding_client: EmbeddingClient) -> list[float]:
    cached = _skill_embedding_cache.get(skill.name)
    if cached is not None:
        return cached
    vector = embedding_client.embed(_skill_text(skill))
    _skill_embedding_cache[skill.name] = vector
    return vector


def rank_skills_by_similarity(
    question: str,
    skills: list[Skill],
    embedding_client: EmbeddingClient,
    top_k: int = 4,
) -> list[Skill]:
    """Returns up to top_k Skills from `skills`, ranked by cosine similarity
    of the question's embedding to each Skill's description+triggers text —
    highest similarity first."""
    if not skills:
        return []

    question_vector = embedding_client.embed(question)
    scored = [
        (_cosine_similarity(question_vector, _get_skill_embedding(skill, embedding_client)), skill)
        for skill in skills
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [skill for _, skill in scored[:top_k]]