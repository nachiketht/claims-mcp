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


def test_json_followed_by_extra_text_is_still_read_as_the_action_input():
    """JSON followed by extra text is still read as the action input."""
    text = "\n".join(
        [
            "Thought: flag it",
            "Action: flag_for_human_review",
            'Action Input: {"employee_id": "E1001", "request": "headphones", "reason": "undetermined"}',
            "",
            "Observation: flagged",
            'check_request_eligibility: {"verdict": "eligible"}',
        ]
    )
    parsed = parse_reply(text)
    assert parsed["kind"] == "tool"
    assert parsed["arguments"]["employee_id"] == "E1001"


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


def _flag_reason(tools: ScriptedTools) -> str:
    return next(args["reason"] for name, args in tools.calls if name == "flag_for_human_review")


def test_the_ceo_pumpkin_spice_request_is_escalated_not_approved():
    """Pumpkin spice is not in the policy, so even the CEO's request is escalated after a review flag."""
    request = "E1005 wants pumpkin spice."
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1005", "item": "pumpkin spice"}),
            _tool(
                "flag_for_human_review",
                {"employee_id": "E1005", "request": request, "reason": "not in policy"},
            ),
        ]
    )
    tools = ScriptedTools(
        results={
            "check_request_eligibility": '{"verdict": "undetermined", "reason": "item_not_in_policy"}'
        }
    )
    events = list(run(request, chat, tools))
    assert events[-1] == {"type": "decision", "text": "escalated"}
    assert not any(event == {"type": "decision", "text": "approved"} for event in events)
    assert "pumpkin spice is not a laptop or a monitor" in _flag_reason(tools)


@pytest.mark.parametrize("word", ["stolen", "lost", "broken"])
def test_stolen_lost_or_broken_is_escalated_with_a_reason_that_names_it(word):
    """Each trigger word escalates, and the review reason names the word and the eligibility result."""
    request = f"E1003 says the laptop was {word}."
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1003", "item": "laptop"}),
            _tool(
                "flag_for_human_review",
                {"employee_id": "E1003", "request": request, "reason": word},
            ),
        ]
    )
    tools = ScriptedTools(results={"check_request_eligibility": '{"verdict": "eligible"}'})
    events = list(run(request, chat, tools))
    assert events[-1] == {"type": "decision", "text": "escalated"}
    reason = _flag_reason(tools)
    assert f"reports the laptop as {word}" in reason
    assert "not a scheduled refresh" in reason
    assert "returned eligible" in reason


def test_a_review_flag_before_eligibility_is_sent_back():
    """A flag before check_request_eligibility is sent back and not recorded."""
    request = "E1003 says the laptop was stolen."
    chat = ScriptedChat(
        [
            _tool(
                "flag_for_human_review",
                {"employee_id": "E1003", "request": request, "reason": "stolen"},
            ),
            _tool("check_request_eligibility", {"employee_id": "E1003", "item": "laptop"}),
            _tool(
                "flag_for_human_review",
                {"employee_id": "E1003", "request": request, "reason": "stolen"},
            ),
        ]
    )
    tools = ScriptedTools(results={"check_request_eligibility": '{"verdict": "eligible"}'})
    events = list(run(request, chat, tools))
    assert {
        "type": "observation",
        "text": "Call check_request_eligibility before flag_for_human_review.",
    } in events
    assert [name for name, _ in tools.calls] == [
        "check_request_eligibility",
        "flag_for_human_review",
    ]
    assert events[-1] == {"type": "decision", "text": "escalated"}


def test_a_repeated_tool_call_is_not_run_again():
    """The same tool with the same arguments is sent back instead of being called twice."""
    check = _tool("check_request_eligibility", {"employee_id": "E1001", "item": "monitor"})
    chat = ScriptedChat(
        [check, check, "Thought: eligible\nFinal Answer: approved", "Decision: approved\nWhy: eligible."]
    )
    tools = ScriptedTools(results={"check_request_eligibility": '{"verdict": "eligible"}'})
    events = list(run("E1001 needs a monitor.", chat, tools))
    assert len(tools.calls) == 1
    assert any(
        event["type"] == "observation" and "already returned a result" in event["text"]
        for event in events
    )
    assert events[-1] == {"type": "decision", "text": "approved"}


def test_a_review_flag_for_a_clear_request_is_sent_back(tmp_path):
    """A clear ineligible request cannot be flagged, and no review record is written."""
    path = tmp_path / "review_queue.json"
    request = "E1002 wants a new laptop because the current one is slow."
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1002", "item": "laptop"}),
            _tool(
                "flag_for_human_review",
                {"employee_id": "E1002", "request": request, "reason": "slow laptop"},
            ),
            "Thought: ineligible\nFinal Answer: denied",
            "Decision: denied\nWhy: ineligible.",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "ineligible"}'},
        queue=JsonFileQueue(path),
    )
    events = list(run(request, chat, tools))
    assert [name for name, _ in tools.calls] == ["check_request_eligibility"]
    assert not path.exists()
    assert events[-1] == {"type": "decision", "text": "denied"}


def test_an_unknown_employee_stops_with_no_decision_and_no_review(tmp_path):
    """An unknown employee ends the run with an error, no decision, and no review record."""
    path = tmp_path / "review_queue.json"
    chat = ScriptedChat(
        [_tool("check_request_eligibility", {"employee_id": "E9999", "item": "laptop"})]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"error": "unknown_employee"}'},
        queue=JsonFileQueue(path),
    )
    events = list(run("E9999 needs a laptop.", chat, tools))
    assert events[-1]["type"] == "error"
    assert "unknown employee" in events[-1]["text"]
    assert not any(event["type"] == "decision" for event in events)
    assert len(chat.prompts) == 1
    assert not path.exists()


def test_a_broken_monitor_is_escalated_when_the_model_does_not_flag():
    """A broken monitor is escalated by the guardrail when the model does not flag it."""
    request = "I am employee E1002, my monitors are broken, can I get new ones"
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1002", "item": "monitors"}),
            "Thought: deny it\nFinal Answer: denied",
            "Thought: still deny\nAction: check_request_eligibility\nAction Input: {not json}",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "ineligible"}'}
    )
    events = list(run(request, chat, tools))
    assert events[-1] == {"type": "decision", "text": "escalated"}
    assert any(event["type"] == "guardrail" for event in events)
    name, arguments = tools.calls[-1]
    assert name == "flag_for_human_review"
    assert arguments["employee_id"] == "E1002"
    assert arguments["request"] == request
    assert "reports the monitors as broken" in arguments["reason"]


def test_a_final_answer_before_eligibility_is_sent_back():
    """A final answer before eligibility is sent back."""
    chat = ScriptedChat(
        [
            "Thought: skip the tool\nFinal Answer: denied",
            _tool("check_request_eligibility", {"employee_id": "E1002", "item": "laptop"}),
            "Thought: the laptop is inside the interval\nFinal Answer: denied",
            "denied",
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "ineligible"}'}
    )
    events = list(run("E1002 wants a new laptop because the current one is slow.", chat, tools))
    assert {"type": "observation", "text": "Call check_request_eligibility before the final answer."} in events
    assert "Call check_request_eligibility before the final answer." in chat.prompts[1]
    assert events[-1] == {"type": "decision", "text": "denied"}


def test_an_undetermined_item_finishes_only_after_a_review_flag():
    """An undetermined item finishes only after a review flag."""
    request = "E1002 wants 500 headphones."
    chat = ScriptedChat(
        [
            "Thought: headphones need no tool\nFinal Answer: denied",
            _tool("check_request_eligibility", {"employee_id": "E1002", "item": "headphones"}),
            "Thought: not in policy\nFinal Answer: denied",
            "denied",
            _tool(
                "flag_for_human_review",
                {
                    "employee_id": "E1002",
                    "request": request,
                    "reason": "item_not_in_policy",
                },
            ),
            "Thought: a person should see this\nFinal Answer: escalated",
            "escalated",
        ]
    )
    tools = ScriptedTools(
        results={
            "check_request_eligibility": '{"verdict": "undetermined", "reason": "item_not_in_policy"}'
        }
    )
    events = list(run(request, chat, tools))
    assert any(
        event["type"] == "observation" and "flag_for_human_review" in event["text"]
        for event in events
    )
    assert events[-1] == {"type": "decision", "text": "escalated"}


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


def test_reflection_changes_a_wrong_draft_and_says_so():
    """A denied draft for an eligible request is changed to approved, and the trace records the change."""
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1001", "item": "monitor"}),
            "Thought: monitors are expensive\nFinal Answer: denied",
            "Decision: approved\nWhy: check_request_eligibility says eligible.",
        ]
    )
    tools = ScriptedTools(results={"check_request_eligibility": '{"verdict": "eligible"}'})
    events = list(run("E1001 needs a monitor.", chat, tools))
    assert {"type": "draft", "text": "denied"} in events
    assert {"type": "reflection_result", "text": "changed denied to approved"} in events
    assert events[-1] == {"type": "decision", "text": "approved"}


def test_reflection_confirms_a_correct_draft():
    """A denied draft for an ineligible request is confirmed."""
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1002", "item": "laptop"}),
            "Thought: inside 24 months\nFinal Answer: denied",
            "Decision: denied\nWhy: the verdict is ineligible, so it is not approved.",
        ]
    )
    tools = ScriptedTools(results={"check_request_eligibility": '{"verdict": "ineligible"}'})
    events = list(run("E1002 wants a new laptop because the current one is slow.", chat, tools))
    assert {"type": "reflection_result", "text": "confirmed denied"} in events
    assert events[-1] == {"type": "decision", "text": "denied"}


def test_reflection_prompt_does_not_give_the_answer():
    """The reflection prompt states the policy but does not tell the model which word to reply with."""
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1001", "item": "monitor"}),
            "Thought: allowed\nFinal Answer: approved",
            "Decision: approved\nWhy: eligible.",
        ]
    )
    tools = ScriptedTools(results={"check_request_eligibility": '{"verdict": "eligible"}'})
    list(run("E1001 needs a monitor.", chat, tools))
    reflection_prompt = chat.prompts[-1]
    assert "Reply with only the word" not in reflection_prompt
    assert "Decision: approved, denied, or escalated" in reflection_prompt


def test_a_reflection_that_breaks_policy_is_rejected_and_retried():
    """A reflection that approves an ineligible request is rejected, and the next draft is checked again."""
    chat = ScriptedChat(
        [
            _tool("check_request_eligibility", {"employee_id": "E1002", "item": "laptop"}),
            "Thought: slow laptop\nFinal Answer: approved",
            "Decision: approved\nWhy: it is slow.",
            "Thought: the verdict is ineligible\nFinal Answer: denied",
            "Decision: denied\nWhy: ineligible.",
        ]
    )
    tools = ScriptedTools(results={"check_request_eligibility": '{"verdict": "ineligible"}'})
    events = list(run("E1002 wants a new laptop because the current one is slow.", chat, tools))
    rejected = [
        event for event in events
        if event["type"] == "observation" and event["text"].startswith("Draft rejected")
    ]
    assert rejected and "ineligible" in rejected[0]["text"]
    assert events[-1] == {"type": "decision", "text": "denied"}


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
        ]
    )
    tools = ScriptedTools(
        results={"check_request_eligibility": '{"verdict": "eligible"}'}
    )
    events = list(run(request, chat, tools))
    sent_back = {
        "type": "observation",
        "text": "Call flag_for_human_review, then Final Answer: escalated.",
    }
    assert events.index(sent_back) < events.index({"type": "decision", "text": "escalated"})


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
