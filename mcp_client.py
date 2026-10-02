import asyncio
import os
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent


class ToolCaller:
    def list_tools(self) -> list:
        raise NotImplementedError

    def call_tool(self, name: str, arguments: dict) -> str:
        raise NotImplementedError


class StdioMcpClient(ToolCaller):
    def list_tools(self) -> list:
        return asyncio.run(_with_server(lambda session: session.list_tools()))

    def call_tool(self, name: str, arguments: dict) -> str:
        result = asyncio.run(
            _with_server(lambda session: session.call_tool(name, arguments))
        )
        if not result.content:
            return ""
        return result.content[0].text


async def _with_server(call):
    env = {}
    if os.environ.get("CLAIMS_LOG"):
        env["CLAIMS_LOG"] = os.environ["CLAIMS_LOG"]
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "server.py")],
        env=env or None,
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await call(session)
    if hasattr(result, "tools"):
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "arguments": {
                    "properties": (tool.input_schema or {}).get("properties", {}),
                    "required": (tool.input_schema or {}).get("required", []),
                },
            }
            for tool in result.tools
        ]
    return result
