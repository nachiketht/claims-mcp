import asyncio
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent


async def main() -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "minimal_server.py")],
    )
    async with (
        stdio_client(server) as (read, write),
        ClientSession(read, write) as session,
    ):
        initialized = await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("ding")
    print("initialize:", initialized.server_info.name)
    print("tools:", [tool.name for tool in tools.tools])
    print("ding:", result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
