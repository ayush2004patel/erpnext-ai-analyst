"""
Unit tests for agent/retrieval.py — cosine similarity + top_k ranking,
using FakeEmbeddingClient (no real embedding model, no Frappe site needed).

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_agent_retrieval
"""

from __future__ import annotations

import unittest

from erpnext_ai_business_analyst.agent import retrieval
from erpnext_ai_business_analyst.agent.retrieval import rank_skills_by_similarity
from erpnext_ai_business_analyst.skills.base import Skill
from erpnext_ai_business_analyst.tests.llm_fakes import FakeEmbeddingClient


def _make_skill(name: str, description: str, triggers: list[str]) -> Skill:
    return Skill(
        name=name, description=description, triggers=triggers,
        params=[], tools_used=[], func=lambda **kwargs: None,
    )


class TestRankSkillsBySimilarity(unittest.TestCase):
    def setUp(self):
        # The cache is process-global and keyed by skill name only — clear
        # it between tests so a name reused across tests with a different
        # fake vector doesn't leak a stale embedding from a prior test.
        retrieval._skill_embedding_cache.clear()

    def test_ranks_by_cosine_similarity_and_respects_top_k(self):
        question = "which items are dead stock"

        skill_identical = _make_skill("skill.identical", "identical match", ["x"])
        skill_close = _make_skill("skill.close", "close match", ["y"])
        skill_orthogonal = _make_skill("skill.orthogonal", "orthogonal match", ["z"])
        skill_opposite = _make_skill("skill.opposite", "opposite match", ["w"])

        embedding_client = FakeEmbeddingClient({
            question: [1.0, 0.0, 0.0],
            "identical match x": [1.0, 0.0, 0.0],
            "close match y": [0.9, 0.1, 0.0],
            "orthogonal match z": [0.0, 1.0, 0.0],
            "opposite match w": [-1.0, 0.0, 0.0],
        })

        ranked = rank_skills_by_similarity(
            question,
            [skill_identical, skill_close, skill_orthogonal, skill_opposite],
            embedding_client,
            top_k=2,
        )

        self.assertEqual([s.name for s in ranked], ["skill.identical", "skill.close"])

    def test_returns_empty_list_for_no_skills(self):
        embedding_client = FakeEmbeddingClient({"q": [1.0, 0.0]})
        ranked = rank_skills_by_similarity("q", [], embedding_client, top_k=4)
        self.assertEqual(ranked, [])

    def test_top_k_larger_than_skill_count_returns_all(self):
        skill_one = _make_skill("skill.one", "desc one", ["t1"])
        skill_two = _make_skill("skill.two", "desc two", ["t2"])
        embedding_client = FakeEmbeddingClient({
            "q": [1.0, 0.0],
            "desc one t1": [1.0, 0.0],
            "desc two t2": [0.0, 1.0],
        })

        ranked = rank_skills_by_similarity("q", [skill_one, skill_two], embedding_client, top_k=10)
        self.assertEqual(len(ranked), 2)

    def test_skill_embeddings_are_cached_across_calls(self):
        skill_cached = _make_skill("skill.cached", "desc cached", ["t"])
        embedding_client = FakeEmbeddingClient({
            "q1": [1.0, 0.0],
            "q2": [1.0, 0.0],
            "desc cached t": [1.0, 0.0],
        })

        rank_skills_by_similarity("q1", [skill_cached], embedding_client, top_k=1)
        rank_skills_by_similarity("q2", [skill_cached], embedding_client, top_k=1)

        # The skill's own text should only be embedded once across both
        # calls (cached); the question is embedded fresh each time.
        skill_text_calls = [c for c in embedding_client.calls if c == "desc cached t"]
        self.assertEqual(len(skill_text_calls), 1)
        self.assertEqual(embedding_client.calls.count("q1"), 1)
        self.assertEqual(embedding_client.calls.count("q2"), 1)