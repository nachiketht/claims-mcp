from mcp.server.mcpserver import MCPServer

from tools import check_request_eligibility as lookup_eligibility
from tools import flag_for_human_review as flag_review
from tools import get_employee_info as lookup_employee
from tools import get_policy_limits as lookup_policy

server = MCPServer("claims")


@server.tool()
def get_employee_info(employee_id: str) -> dict:
    return lookup_employee(employee_id)


@server.tool()
def get_policy_limits(role: str) -> dict:
    return lookup_policy(role)


@server.tool()
def check_request_eligibility(employee_id: str, item: str) -> dict:
    return lookup_eligibility(employee_id, item)


@server.tool()
def flag_for_human_review(employee_id: str, request: str, reason: str) -> dict:
    return flag_review(employee_id, request, reason)


if __name__ == "__main__":
    server.run("stdio")
