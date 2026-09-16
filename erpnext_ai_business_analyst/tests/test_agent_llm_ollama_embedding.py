"""
Tests for agent/llm/ollama_embedding_client.py. Mocks requests.post — no
real Ollama server needed to run these.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_agent_llm_ollama_embedding
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import frappe

from erpnext_ai_business_analyst.agent.llm.ollama_embedding_client import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_HOST,
    OllamaEmbeddingClient,
)


class TestOllamaEmbeddingClient(unittest.TestCase):
    def test_uses_default_model_and_host_when_unconfigured(self):
        with patch.dict(frappe.conf, {"ollama_embedding_model": None, "ollama_host": None}):
            client = OllamaEmbeddingClient()
        self.assertEqual(client.model, DEFAULT_EMBEDDING_MODEL)
        self.assertEqual(client.host, DEFAULT_HOST)

    def test_reads_model_and_host_from_site_config(self):
        with patch.dict(frappe.conf, {
            "ollama_embedding_model": "mxbai-embed-large",
            "ollama_host": "http://ollama-box:11434/",
        }):
            client = OllamaEmbeddingClient()
        self.assertEqual(client.model, "mxbai-embed-large")
        self.assertEqual(client.host, "http://ollama-box:11434")  # trailing slash stripped

    def test_explicit_args_override_site_config(self):
        client = OllamaEmbeddingClient(model="explicit-model", host="http://explicit-host:1234")
        self.assertEqual(client.model, "explicit-model")
        self.assertEqual(client.host, "http://explicit-host:1234")

    @patch("erpnext_ai_business_analyst.agent.llm.ollama_embedding_client.requests.post")
    def test_embed_posts_payload_and_returns_vector(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = OllamaEmbeddingClient(model="test-model", host="http://localhost:11434")
        result = client.embed("some text to embed")

        self.assertEqual(result, [0.1, 0.2, 0.3])

        called_url = mock_post.call_args[0][0]
        called_kwargs = mock_post.call_args[1]
        self.assertEqual(called_url, "http://localhost:11434/api/embeddings")
        self.assertEqual(called_kwargs["json"], {"model": "test-model", "prompt": "some text to embed"})

    @patch("erpnext_ai_business_analyst.agent.llm.ollama_embedding_client.requests.post")
    def test_raises_on_unexpected_response_shape(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "shape"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = OllamaEmbeddingClient(model="test-model", host="http://localhost:11434")
        with self.assertRaises(RuntimeError):
            client.embed("text")