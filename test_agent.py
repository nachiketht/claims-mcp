import json

import pytest

from agent import parse_reply, run
from review_queue import JsonFileQueue


class ScriptedChat:
    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.replies.pop(0)


class ScriptedTools:
    def __init__(self, tools=None, results=None, queue=None):
        self.tools = tools if tools is not None else [
            "get_employee_info",
            "get_policy_limits",
            "check_request_eligibility",
            "flag_for_human_review",
        ]
        self.results = results or {}
        self.queue = queue
        self.calls = []

    def list_tools(self) -> list:
        return self.tools

    def call_tool(self, name: str, arguments: dict) -> str:
        self.calls.append((name, arguments))
        if name == "flag_for_human_review" and self.queue is not None:
            self.queue.append(arguments)
        return self.results.get(name, "{}")


def _tool(name: str, arguments: dict) -> str:
    return f"Thought: use {name}\nAction: {name}\nAction Input: {json.dumps(arguments)}"


def test_parser_reads_thought_action_and_input():
    """A tool reply has a thought, an action, and a JSON action input."""
    parsed = parse_reply(_tool("get_employee_info", {"employee_id": "E1001"}))
    assert parsed == {
        "kind": "tool",
        "thought": "use get_employee_info",
        "action": "get_employee_info",
        "arguments": {"employee_id": "E1001"},
    }


def test_parser_reads_a_final_answer():
    """A final reply has a thought and the answer text."""
    parsed = parse_reply("Thought: the monitor is allowed\nFinal Answer: approved")
    assert parsed == {
        "kind": "final",
        "thought": "the monitor is allowed",
        "text": "approved",
    }


def test_parser_rejects_text_with_no_labels():
    """Text with no Thought, Action, or Final Answer labels is unreadable."""
    assert parse_reply("hello")["kind"] == "unreadable"


def test_parser_rejects_an_unknown_tool_name():
    """An action that is not one of the four tools is rejected."""
    parsed = parse_reply(_tool("send_email", {"employee_id": "E1001"}))
    assert parsed["kind"] == "unknown_tool"


def test_parser_reads_json_inside_a_code_fence():
    """JSON wrapped in a markdown fence is still read as the action input."""
    text = "\n".join(
        [
            "Thought: fenced",
            "Action: get_employee_info",
            "Action Input:",
            "```json",
            '{"employee_id": "E1001"}',
            "```",
        ]
    )
    assert parse_reply(text)["arguments"] == {"employee_id": "E1001"}


def test_bad_json_is_returned_as_the_observation():
    """Action input that is not JSON is returned as the observation."""
    reply = "Thought: bad\nAction: get_employee_info\nAction Input: {not json}"
    chat = ScriptedChat([reply] + ["still bad"] * 7)
    events = list(run("E1001 needs a monitor.", chat, ScriptedTools()))
    assert {"type": "observation", "text": "{not json}"} in events
    assert chat.prompts[1].endswith("{not json}") or "{not json}" in chat.prompts[1]


def test_a_finished_run_reports_model_time_tool_time_and_total_time():
    """A finished run reports model time, tool time, and total time."""
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1001", "item": "monitor"}),
            "Thought: allowed\nFinal Answer: approved",
            "approved",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "eligible"}'}
    )
    events = list(run("E1001 needs a monitor.", chat, tools))
    latency = next(event for event in events if event["type"] == "latency")
    assert "model" in latency["text"] and "tools" in latency["text"]
    assert "total" in latency["text"]
    assert events.index(latency) < events.index({"type": "decision", "text": "approved"})


def test_loop_stops_when_a_tool_name_is_missing():
    """The loop stops before asking the model when a tool name is missing."""
    chat = ScriptedChat([])
    events = list(run("E1001 needs a monitor.", chat, ScriptedTools(tools=["get_employee_info"])))
    assert events[0]["type"] == "error"
    assert "get_policy_limits" in events[0]["text"]
    assert chat.prompts == []


def test_loop_calls_the_tool_the_model_names_and_stops_on_a_final_answer():
    """The loop calls the tool the model names, then stops when the final answer is allowed."""
    chat = ScriptedChat(
        [
            _tool("get_employee_info", {"employee_id": "E1001"}),
            _tool("check_request_eligibility", {"employee_id": "E1001", "item": "monitor"}),
            "Thought: allowed\nFinal Answer: approved",
            "approved",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "eligible"}'}
    )
    events = list(run("E1001 needs a monitor.", chat, tools))
    assert tools.calls[0] == ("get_employee_info", {"employee_id": "E1001"})
    assert events[-1] == {"type": "decision", "text": "approved"}


def test_bad_format_is_sent_back_and_counts_as_a_step():
    """An unreadable reply is sent back to the model and counts as a step."""
    chat = ScriptedChat(
        [
            "hello",
            _tool("check_request_eligibility", {"employee_id": "E1001", "item": "monitor"}),
            "Thought: allowed\nFinal Answer: approved",
            "approved",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "eligible"}'}
    )
    events = list(run("E1001 needs a monitor.", chat, tools))
    assert {"type": "observation", "text": "hello"} in events
    assert "hello" in chat.prompts[1]
    assert events[-1]["type"] == "decision"


def test_loop_stops_at_eight_steps_when_there_is_no_final_answer():
    """Eight replies with no final answer end the run with no decision."""
    chat = ScriptedChat(["not a trace"] * 8)
    events = list(run("E1001 needs a monitor.", chat, ScriptedTools()))
    assert len(chat.prompts) == 8
    assert events[-1] == {"type": "error", "text": "no decision"}
    assert not any(event["type"] == "decision" for event in events)


def test_reflection_is_a_second_model_call_and_its_text_is_what_the_draft_check_reads():
    """Reflection is a second model call, and the draft check reads that text."""
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1001", "item": "monitor"}),
            "Thought: first draft\nFinal Answer: denied",
            "approved",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "eligible"}'}
    )
    events = list(run("E1001 needs a monitor.", chat, tools))
    assert len(chat.prompts) == 3
    assert events[-1] == {"type": "decision", "text": "approved"}


def test_eligible_monitor_request_does_not_write_a_review(tmp_path):
    """An eligible monitor request for E1001 is approved and leaves the queue empty."""
    path = tmp_path / "review_queue.json"
    chat = ScriptedChat(
        [
            _tool("get_employee_info", {"employee_id": "E1001"}),
            _tool("get_policy_limits", {"role": "engineer"}),
            _tool("check_request_eligibility", {"employee_id": "E1001", "item": "monitor"}),
            "Thought: within policy\nFinal Answer: approved",
            "approved",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "eligible"}'},
        queue=JsonFileQueue(path),
    )
    events = list(run("E1001 needs a monitor.", chat, tools))
    assert events[-1] == {"type": "decision", "text": "approved"}
    assert not path.exists()


def test_approved_draft_for_a_stolen_laptop_is_sent_back():
    """An approved draft for a stolen laptop is sent back because no review was recorded."""
    request = "E1003 says the laptop was stolen."
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1003", "item": "laptop"}),
            "Thought: the refresh elapsed\nFinal Answer: approved",
            "approved",
            _tool(
                "flag_for_human_review",
                {
                    "employee_id": "E1003",
                    "request": request,
                    "reason": "theft",
                },
            ),
            "Thought: a person should see this\nFinal Answer: escalated",
            "escalated",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "eligible"}'}
    )
    events = list(run(request, chat, tools))
    rejected = {"type": "observation", "text": "Draft rejected: approved"}
    assert events.index(rejected) < events.index({"type": "decision", "text": "escalated"})


def test_stolen_laptop_finishes_only_after_a_review_record(tmp_path):
    """A stolen laptop finishes only after flag_for_human_review writes a record."""
    request = "E1003 says the laptop was stolen."
    path = tmp_path / "review_queue.json"
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1003", "item": "laptop"}),
            "Thought: the refresh elapsed\nFinal Answer: approved",
            "approved",
            _tool(
                "flag_for_human_review",
                {
                    "employee_id": "E1003",
                    "request": request,
                    "reason": "theft",
                },
            ),
            "Thought: a person should see this\nFinal Answer: escalated",
            "escalated",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "eligible"}'},
        queue=JsonFileQueue(path),
    )
    events = list(run(request, chat, tools))
    assert events[-1] == {"type": "decision", "text": "escalated"}
    assert path.exists()
    assert tools.calls[-2][0] == "flag_for_human_review" or any(
        name == "flag_for_human_review" for name, _ in tools.calls
    )


def test_unreachable_model_raises_and_writes_no_decision(tmp_path):
    """An unreachable model raises, and no decision file is written."""
    path = tmp_path / "decision.txt"

    class Unreachable:
        def complete(self, prompt: str) -> str:
            raise RuntimeError(
                "cannot reach the model qwen3:8b at http://host.docker.internal:11434"
            )

    with pytest.raises(RuntimeError, match="qwen3:8b"):
        for event in run("E1001 needs a monitor.", Unreachable(), ScriptedTools()):
            if event["type"] == "decision":
                path.write_text(event["text"])
    assert not path.exists()
