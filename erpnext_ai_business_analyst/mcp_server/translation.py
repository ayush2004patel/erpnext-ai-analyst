"""
Pure translation between the Tool contract (tools/base.py) and MCP's JSON
schema shapes. Deliberately has no dependency on the MCP SDK itself, or on
Frappe — this is the logic worth unit testing directly; the SDK wiring in
server.py is thin plumbing around it.
"""

from __future__ import annotations

from erpnext_ai_business_analyst.tools.base import Tool, ToolResult, ToolStatus

_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
}


def tool_to_mcp_schema(tool: Tool) -> dict:
    """Builds an MCP tool definition (name/description/inputSchema) from a
    Tool's declared params. A param is listed as JSON-Schema "required"
    only when it's both required=True AND has no default — matching
    Tool._validate_params's own definition of "must be supplied"."""
    properties = {}
    required = []

    for param in tool.params:
        schema = {"type": _TYPE_MAP.get(param.type, "string")}
        if param.description:
            schema["description"] = param.description
        properties[param.name] = schema

        if param.required and param.default is None:
            required.append(param.name)

    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def tool_result_to_mcp_response(result: ToolResult) -> dict:
    """Shapes a ToolResult into the JSON payload returned to the MCP client.
    Error/denied results collapse to a single {"error": ...} shape — MCP
    clients don't need our internal ToolStatus distinctions, just whether
    it worked and, if not, why."""
    if result.status == ToolStatus.ERROR:
        return {"error": result.error or result.denied_reason or "Unknown error"}

    return {
        "status": result.status,
        "data": result.data,
        "query_meta": vars(result.query_meta) if result.query_meta else None,
    }