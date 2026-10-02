import json

from mcp_client import StdioMcpClient


def test_server_lists_and_runs_all_four_tools_over_stdio(tmp_path, monkeypatch):
    """server.py, started through the MCP client, lists the four tools and answers each one."""
    queue = tmp_path / "review_queue.json"
    monkeypatch.setenv("CLAIMS_AS_OF", "2026-10-02")
    monkeypatch.setenv("CLAIMS_REVIEW_QUEUE", str(queue))
    with StdioMcpClient() as client:
        names = sorted(tool["name"] for tool in client.list_tools())
        employee = json.loads(client.call_tool("get_employee_info", {"employee_id": "E1001"}))
        policy = json.loads(client.call_tool("get_policy_limits", {"role": "manager"}))
        monitor = json.loads(
            client.call_tool(
                "check_request_eligibility", {"employee_id": "E1001", "item": "monitor"}
            )
        )
        laptop = json.loads(
            client.call_tool(
                "check_request_eligibility", {"employee_id": "E1002", "item": "laptop"}
            )
        )
        tablet = json.loads(
            client.call_tool(
                "check_request_eligibility", {"employee_id": "E1004", "item": "drawing tablet"}
            )
        )
        review = json.loads(
            client.call_tool(
                "flag_for_human_review",
                {
                    "employee_id": "E1003",
                    "request": "E1003 says the laptop was stolen.",
                    "reason": "The request says the laptop is stolen.",
                },
            )
        )
    assert names == [
        "check_request_eligibility",
        "flag_for_human_review",
        "get_employee_info",
        "get_policy_limits",
    ]
    assert employee["tenure_months"] == 51
    assert policy == {"laptop": 24, "monitor": 36}
    assert monitor == {"verdict": "eligible"}
    assert laptop == {"verdict": "ineligible"}
    assert tablet == {"verdict": "undetermined", "reason": "item_not_in_policy"}
    assert review["employee_id"] == "E1003"
    assert json.loads(queue.read_text())[0] == review
