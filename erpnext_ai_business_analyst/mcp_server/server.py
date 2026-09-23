"""
MCP server exposing the ToolRegistry's read-only inventory Tools to
external MCP clients (e.g. Claude Desktop). Skills/Planner are
deliberately NOT exposed — see ARCHITECTURE.md §8: Skills are stateful/
multi-hop and don't map to a single MCP tool call.

Uses the LOWLEVEL mcp.server.Server, not the high-level MCPServer/
@mcp.tool() convenience API. MCPServer.add_tool() derives each tool's
schema by introspecting a Python function's type hints
(Tool.from_function()) — that doesn't fit registering tools dynamically
from a runtime ToolRegistry with no fixed function signatures. The
lowlevel Server lets us supply the tool list and dispatch logic
explicitly, using the schemas translation.py already builds from each
Tool's own declared params. Confirmed against the real installed
Server.__init__ signature (mcp 2.x) rather than guessed.

Runs as a dedicated, restricted Frappe user — never Administrator — so
each Tool's existing frappe.has_permission checks genuinely apply, scoped
to whatever that user's role is allowed to read. Create the user once via
setup/mcp_service_user.py, then configure it:
    bench --site <site> set-config mcp_service_user "mcp-service@yoursite.local"

Fails fast (refuses to start) if mcp_service_user isn't configured, or is
configured to a User that doesn't exist — never silently falls back to
Administrator.
"""

from __future__ import annotations

import json
import os

import anyio
import frappe
from mcp import types
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server

from erpnext_ai_business_analyst.mcp_server.translation import (
    tool_result_to_mcp_response,
    tool_to_mcp_schema,
)
from erpnext_ai_business_analyst.tools.registry import ToolRegistry


class MCPConfigurationError(Exception):
    """Raised when the MCP server can't start due to missing/invalid config."""


def _get_configured_service_user() -> str:
    service_user = frappe.conf.get("mcp_service_user")
    if not service_user:
        raise MCPConfigurationError(
            "mcp_service_user is not set in site_config.json. Refusing to start the "
            "MCP server rather than falling back to Administrator. Create the "
            "restricted service user first (see erpnext_ai_business_analyst.setup."
            "mcp_service_user.create_mcp_service_user), then run:\n"
            '    bench --site <site> set-config mcp_service_user "<email>"'
        )
    if not frappe.db.exists("User", service_user):
        raise MCPConfigurationError(
            f"mcp_service_user is set to {service_user!r}, but no such User exists. "
            "Create it first via erpnext_ai_business_analyst.setup.mcp_service_user."
            "create_mcp_service_user."
        )
    return service_user


def build_lowlevel_server(tool_registry: ToolRegistry) -> Server:
    async def on_list_tools(
        ctx: ServerRequestContext, params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        tools = [
            types.Tool(
                name=schema["name"],
                description=schema["description"],
                input_schema=schema["inputSchema"],
            )
            for schema in (tool_to_mcp_schema(t) for t in tool_registry.all())
        ]
        return types.ListToolsResult(tools=tools)

    async def on_call_tool(
        ctx: ServerRequestContext, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        try:
            tool = tool_registry.get_tool(params.name)
        except KeyError:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Unknown tool: {params.name!r}")],
                is_error=True,
            )

        # Tool.__call__ is synchronous (blocking DB calls) — acceptable here:
        # a local stdio server driven by one client (e.g. Claude Desktop)
        # handles one request at a time in practice, so blocking the loop
        # for the duration of a single query isn't a real contention issue.
        result = tool(**(params.arguments or {}))
        response = tool_result_to_mcp_response(result)
        is_error = "error" in response

        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(response, default=str))],
            is_error=is_error,
        )

    return Server(
        "erpnext-ai-business-analyst",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def _serve(server: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """Entry point — connects to the site, verifies config, starts the
    stdio MCP server. Intended to be launched by an MCP client (e.g.
    Claude Desktop's config) as a subprocess, not run interactively."""
    site = os.environ.get("MCP_FRAPPE_SITE") or frappe.local.site
    frappe.init(site=site)
    frappe.connect()
    try:
        service_user = _get_configured_service_user()
        frappe.set_user(service_user)
        server = build_lowlevel_server(ToolRegistry.get())
        anyio.run(_serve, server)
    finally:
        frappe.destroy()


if __name__ == "__main__":
    run()