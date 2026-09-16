"""
Unit tests for mcp_server/translation.py — pure schema/response shaping
logic, no MCP SDK, no Frappe site needed.

Run with:
    bench --site business-analyst run-tests \
        --module erpnext_ai_business_analyst.tests.test_mcp_server_translation
"""

from __future__ import annotations

import unittest

from erpnext_ai_business_analyst.mcp_server.translation import (
    tool_result_to_mcp_response,
    tool_to_mcp_schema,
)
from erpnext_ai_business_analyst.tools.base import QueryMeta, Tool, ToolParam, ToolResult, ToolStatus


def _noop(**kwargs):
    return ToolResult(status=ToolStatus.OK)


class TestToolToMcpSchema(unittest.TestCase):
    def test_maps_param_types_and_required_flags(self):
        tool = Tool(
            name="inventory.get_reorder_status",
            description="Reorder status per item+warehouse.",
            params=[
                ToolParam("item_code", "str", required=False),
                ToolParam("window_days", "int", required=False, default=90),
                ToolParam("below_rol_qty", "bool", required=False, default=False),
            ],
            func=_noop,
        )

        schema = tool_to_mcp_schema(tool)

        self.assertEqual(schema["name"], "inventory.get_reorder_status")
        self.assertEqual(schema["description"], tool.description)
        props = schema["inputSchema"]["properties"]
        self.assertEqual(props["item_code"]["type"], "string")
        self.assertEqual(props["window_days"]["type"], "integer")
        self.assertEqual(props["below_rol_qty"]["type"], "boolean")
        self.assertEqual(schema["inputSchema"]["required"], [])  # none truly required here

    def test_required_param_with_no_default_is_listed_as_required(self):
        tool = Tool(
            name="some.tool",
            description="desc",
            params=[ToolParam("mandatory_field", "str", required=True)],
            func=_noop,
        )
        schema = tool_to_mcp_schema(tool)
        self.assertEqual(schema["inputSchema"]["required"], ["mandatory_field"])

    def test_param_description_is_included_when_present(self):
        tool = Tool(
            name="some.tool",
            description="desc",
            params=[ToolParam("field", "str", required=False, description="A field.")],
            func=_noop,
        )
        schema = tool_to_mcp_schema(tool)
        self.assertEqual(schema["inputSchema"]["properties"]["field"]["description"], "A field.")

    def test_unknown_param_type_falls_back_to_string(self):
        tool = Tool(
            name="some.tool",
            description="desc",
            params=[ToolParam("odd", "something_unmapped", required=False)],
            func=_noop,
        )
        schema = tool_to_mcp_schema(tool)
        self.assertEqual(schema["inputSchema"]["properties"]["odd"]["type"], "string")


class TestToolResultToMcpResponse(unittest.TestCase):
    def test_ok_result_includes_data_and_query_meta(self):
        result = ToolResult(
            status=ToolStatus.OK,
            data=[{"item_code": "X"}],
            query_meta=QueryMeta(doctype="Bin", filters={}, fields=["item_code"], row_count=1),
        )
        response = tool_result_to_mcp_response(result)
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"], [{"item_code": "X"}])
        self.assertEqual(response["query_meta"]["doctype"], "Bin")

    def test_error_result_returns_error_message(self):
        result = ToolResult(status=ToolStatus.ERROR, error="Missing read permission on 'Bin'")
        response = tool_result_to_mcp_response(result)
        self.assertEqual(response, {"error": "Missing read permission on 'Bin'"})

    def test_error_result_falls_back_to_denied_reason(self):
        result = ToolResult(status=ToolStatus.ERROR, denied_reason="Permission denied")
        response = tool_result_to_mcp_response(result)
        self.assertEqual(response, {"error": "Permission denied"})

    def test_result_with_no_query_meta_returns_none(self):
        result = ToolResult(status=ToolStatus.OK, data=[])
        response = tool_result_to_mcp_response(result)
        self.assertIsNone(response["query_meta"])