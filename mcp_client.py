"""MCP client that connects to MCP servers and exposes their tools to LangChain."""

import json
from contextlib import AsyncExitStack
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, create_model

from config import McpServerConfig


class McpClient:
    """Manages connections to multiple MCP servers and exposes their tools."""

    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tools: list[StructuredTool] = []

    async def connect(self, servers: list[McpServerConfig]) -> None:
        """Connect to all configured MCP servers."""
        for server in servers:
            try:
                await self._connect_server(server)
            except Exception as e:
                print(f"[ERROR] Failed to connect to MCP server '{server.name}': {e}")
                if hasattr(e, "exceptions"):
                    for sub_err in e.exceptions:
                        print(f"  -> {type(sub_err).__name__}: {sub_err}")

    async def _connect_server(self, server: McpServerConfig) -> None:
        """Connect to a single MCP server and register its tools."""
        if server.transport == "sse":
            transport = await self._exit_stack.enter_async_context(
                sse_client(server.url)
            )
        else:
            params = StdioServerParameters(
                command=server.command,
                args=server.args,
                env=server.env if server.env else None,
            )
            transport = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )

        read_stream, write_stream = transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        self._sessions[server.name] = session

        response = await session.list_tools()
        for tool in response.tools:
            langchain_tool = self._wrap_as_langchain_tool(session, tool)
            self._tools.append(langchain_tool)

        print(f"[INFO] Connected to '{server.name}' — {len(response.tools)} tool(s)")

    def _wrap_as_langchain_tool(self, session: ClientSession, mcp_tool: Any) -> StructuredTool:
        """Convert an MCP tool into a LangChain StructuredTool."""
        input_model = self._build_input_model(mcp_tool.name, mcp_tool.inputSchema)

        async def call_tool(**kwargs: Any) -> str:
            result = await session.call_tool(mcp_tool.name, arguments=kwargs)
            return json.dumps([c.text for c in result.content if hasattr(c, "text")])

        return StructuredTool(
            name=mcp_tool.name,
            description=mcp_tool.description or mcp_tool.name,
            coroutine=call_tool,
            args_schema=input_model,
        )

    @staticmethod
    def _build_input_model(name: str, schema: dict) -> type[BaseModel]:
        """Dynamically create a Pydantic model from a JSON schema."""
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        TYPE_MAP = {"string": str, "integer": int, "number": float, "boolean": bool}
        fields: dict[str, Any] = {}
        for field_name, field_schema in properties.items():
            field_type = TYPE_MAP.get(field_schema.get("type", "string"), str)
            default = ... if field_name in required else None
            fields[field_name] = (field_type, default)

        return create_model(f"{name}_Input", **fields)

    @property
    def tools(self) -> list[StructuredTool]:
        return self._tools

    async def cleanup(self) -> None:
        """Close all MCP server connections."""
        await self._exit_stack.aclose()
        print("[INFO] All MCP connections closed")
