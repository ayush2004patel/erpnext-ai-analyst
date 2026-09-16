"""
Tests for the MCP server's fail-fast configuration check
(_get_configured_service_user) — never silently falls back to
Administrator.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_mcp_server_config
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_ai_business_analyst.mcp_server.server import (
    MCPConfigurationError,
    _get_configured_service_user,
)


class TestGetConfiguredServiceUser(FrappeTestCase):
    def test_raises_when_unset(self):
        with patch.dict(frappe.conf, {"mcp_service_user": None}):
            with self.assertRaises(MCPConfigurationError):
                _get_configured_service_user()

    def test_raises_when_configured_user_does_not_exist(self):
        with patch.dict(frappe.conf, {"mcp_service_user": "does-not-exist@example.com"}):
            with self.assertRaises(MCPConfigurationError):
                _get_configured_service_user()

    def test_returns_email_when_configured_user_exists(self):
        # Administrator always exists on any real Frappe site — used here
        # only to verify the "exists" branch, not as a recommendation to
        # actually configure mcp_service_user as Administrator.
        with patch.dict(frappe.conf, {"mcp_service_user": "Administrator"}):
            result = _get_configured_service_user()
        self.assertEqual(result, "Administrator")