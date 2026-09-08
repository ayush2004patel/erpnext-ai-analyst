"""
Tests for agent/llm/ollama_client.py. Mocks requests.post — no real Ollama
server needed to run these.

Note: frappe.conf is a frappe._dict, not a plain object — patch.object()
doesn't work on it (its __dict__ is the config data itself, not normal
instance attributes). Use patch.dict() instead, which works on any mapping.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_agent_llm_ollama
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import frappe

from erpnext_ai_business_analyst.agent.llm.ollama_client import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    OllamaClient,
)


class TestOllamaClient(unittest.TestCase):
    def test_uses_default_model_and_host_when_unconfigured(self):
        with patch.dict(frappe.conf, {"ollama_model": None, "ollama_host": None}):
            client = OllamaClient()
        self.assertEqual(client.model, DEFAULT_MODEL)
        self.assertEqual(client.host, DEFAULT_HOST)

    def test_reads_model_and_host_from_site_config(self):
        with patch.dict(frappe.conf, {
            "ollama_model": "qwen2.5:7b-instruct",
            "ollama_host": "http://ollama-box:11434/",
        }):
            client = OllamaClient()
        self.assertEqual(client.model, "qwen2.5:7b-instruct")
        self.assertEqual(client.host, "http://ollama-box:11434")  # trailing slash stripped

    def test_explicit_args_override_site_config(self):
        client = OllamaClient(model="explicit-model", host="http://explicit-host:1234")
        self.assertEqual(client.model, "explicit-model")
        self.assertEqual(client.host, "http://explicit-host:1234")

    @patch("erpnext_ai_business_analyst.agent.llm.ollama_client.requests.post")
    def test_complete_posts_chat_payload_and_returns_content(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"role": "assistant", "content": '{"action": "CONCLUDE"}'}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = OllamaClient(model="test-model", host="http://localhost:11434")
        result = client.complete("system prompt text", "user prompt text", max_tokens=200)

        self.assertEqual(result, '{"action": "CONCLUDE"}')

        called_url = mock_post.call_args[0][0]
        called_kwargs = mock_post.call_args[1]
        self.assertEqual(called_url, "http://localhost:11434/api/chat")
        payload = called_kwargs["json"]
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["messages"][0], {"role": "system", "content": "system prompt text"})
        self.assertEqual(payload["messages"][1], {"role": "user", "content": "user prompt text"})
        self.assertEqual(payload["options"]["num_predict"], 200)

    @patch("erpnext_ai_business_analyst.agent.llm.ollama_client.requests.post")
    def test_raises_on_unexpected_response_shape(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "shape"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = OllamaClient(model="test-model", host="http://localhost:11434")
        with self.assertRaises(RuntimeError):
            client.complete("sys", "user")