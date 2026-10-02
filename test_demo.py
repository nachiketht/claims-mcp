from demo import FlipFirstDraft


class Replies:
    def __init__(self, replies):
        self.replies = list(replies)

    def complete(self, prompt: str) -> str:
        return self.replies.pop(0)


def test_fault_injection_flips_only_the_first_final_answer():
    """The first Final Answer is swapped, and a tool call or a later answer passes through."""
    chat = FlipFirstDraft(
        Replies(
            [
                "Thought: check\nAction: check_request_eligibility\nAction Input: {}",
                "Thought: inside 24 months\nFinal Answer: denied",
                "Decision: denied\nWhy: ineligible.",
                "Thought: again\nFinal Answer: denied",
            ]
        )
    )
    assert "Action: check_request_eligibility" in chat.complete("")
    assert chat.complete("").endswith("Final Answer: approved")
    assert chat.complete("") == "Decision: denied\nWhy: ineligible."
    assert chat.complete("").endswith("Final Answer: denied")


def test_fault_injection_skips_a_tool_call_that_also_has_a_final_answer():
    """A reply with an Action line is a tool call, so it is not flipped, and the next real draft is."""
    mixed = (
        "Thought: check again\nAction: check_request_eligibility\n"
        'Action Input: {"employee_id": "E1002", "item": "laptop"}\nFinal Answer: denied'
    )
    chat = FlipFirstDraft(Replies([mixed, "Thought: inside 24 months\nFinal Answer: denied"]))
    assert chat.complete("") == mixed
    assert chat.complete("").endswith("Final Answer: approved")
