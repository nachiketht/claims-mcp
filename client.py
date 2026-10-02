import asyncio
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent


async def main() -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "server.py")],
    )
    async with (
        stdio_client(server) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        employee = await session.call_tool(
            "get_employee_info", {"employee_id": "E1001"}
        )
        policy = await session.call_tool("get_policy_limits", {"role": "manager"})
        monitor = await session.call_tool(
            "check_request_eligibility",
            {"employee_id": "E1001", "item": "monitor"},
        )
        laptop = await session.call_tool(
            "check_request_eligibility",
            {"employee_id": "E1002", "item": "laptop"},
        )
        review = await session.call_tool(
            "flag_for_human_review",
            {
                "employee_id": "E1003",
                "request": "E1003 says the laptop was stolen.",
                "reason": "theft",
            },
        )
    print("tools:", [tool.name for tool in tools.tools])
    print("get_employee_info E1001:", employee.content[0].text)
    print("get_policy_limits manager:", policy.content[0].text)
    print("check_request_eligibility E1001 monitor:", monitor.content[0].text)
    print("check_request_eligibility E1002 laptop:", laptop.content[0].text)
    print("flag_for_human_review E1003:", review.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
