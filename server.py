import logging
import os
import sys

from mcp.server.mcpserver import MCPServer

from tools import check_request_eligibility as lookup_eligibility
from tools import flag_for_human_review as flag_review
from tools import get_employee_info as lookup_employee
from tools import get_policy_limits as lookup_policy

server = MCPServer("claims")


@server.tool()
def get_employee_info(employee_id: str) -> dict:
    """Return role, tenure in months, and equipment for an employee id."""
    return lookup_employee(employee_id)


@server.tool()
def get_policy_limits(role: str) -> dict:
    """Return the refresh interval in months for a role: engineer, manager, or ceo."""
    return lookup_policy(role)


@server.tool()
def check_request_eligibility(employee_id: str, item: str) -> dict:
    """Return eligible, ineligible, or undetermined. An item other than a laptop or a monitor is undetermined."""
    return lookup_eligibility(employee_id, item)


@server.tool()
def flag_for_human_review(employee_id: str, request: str, reason: str) -> dict:
    """Record a review when a request is stolen, lost, broken, or undetermined."""
    return flag_review(employee_id, request, reason)


def _enable_claim_log() -> None:
    path = os.environ.get("CLAIMS_LOG")
    if not path:
        return
    claim_log = logging.getLogger("claims")
    claim_log.setLevel(logging.INFO)
    claim_log.propagate = False
    formatter = logging.Formatter("%(message)s")
    file_handler = logging.FileHandler(path, mode="a")
    stream_handler = logging.StreamHandler(sys.stderr)
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    claim_log.addHandler(file_handler)
    claim_log.addHandler(stream_handler)


if __name__ == "__main__":
    _enable_claim_log()
    server.run("stdio")
