import logging
import os
import re
import sys
from pathlib import Path

from agent import parse_reply, run
from llm import ChatModel, OllamaChat

REQUESTS = {
    "E1001": ("E1001 needs a monitor.", "evidence/05-approve-monitor.txt"),
    "E1002": (
        "E1002 wants a new laptop because the current one is slow.",
        "evidence/06-deny-laptop.txt",
    ),
    "E1003": (
        "E1003 says the laptop was stolen.",
        "evidence/07-escalate-stolen.txt",
    ),
    "E1004": (
        "E1004 needs a drawing tablet.",
        "evidence/08-escalate-tablet.txt",
    ),
    "E1005": (
        "E1005 needs a new laptop because a new one launched.",
        "evidence/09-approve-ceo-laptop.txt",
    ),
    "ceo-monitor": (
        "E1005 needs a new monitor.",
        "evidence/12-deny-ceo-monitor.txt",
    ),
    "broken": (
        "E1002 says the monitor is broken.",
        "evidence/13-escalate-broken-monitor.txt",
    ),
    "lost": (
        "E1004 lost the laptop on a trip.",
        "evidence/14-escalate-lost-laptop.txt",
    ),
    "pumpkin": (
        "E1005 wants pumpkin spice.",
        "evidence/15-escalate-ceo-pumpkin-spice.txt",
    ),
    "unknown": (
        "E9999 needs a laptop.",
        "evidence/16-unknown-employee.txt",
    ),
    "reflection-fix": (
        "E1002 wants a new laptop because the current one is slow.",
        "evidence/17-reflection-corrects-draft.txt",
    ),
}


def main(argv: list[str] | None = None) -> int:
    chosen = sys.argv[1:] if argv is None else argv
    keys = chosen or list(REQUESTS)
    unknown = [key for key in keys if key not in REQUESTS]
    if unknown:
        print("usage: python demo.py [" + "|".join(REQUESTS) + "]")
        return 2
    for key in keys:
        sentence, path = REQUESTS[key]
        chat = FlipFirstDraft(OllamaChat()) if key == "reflection-fix" else None
        error = _run_one(sentence, Path(path), chat)
        if error:
            print(error)
            return 1
    return 0


class FlipFirstDraft(ChatModel):
    """Fault injection: the model's first Final Answer is swapped to the opposite word."""

    FLIPS = {"approved": "denied", "denied": "approved"}

    def __init__(self, inner: ChatModel) -> None:
        self.inner = inner
        self.flipped = False

    def complete(self, prompt: str) -> str:
        reply = self.inner.complete(prompt)
        match = re.search(r"(Final Answer:\s*)(approved|denied)", reply, re.I)
        if self.flipped or match is None or parse_reply(reply)["kind"] != "final":
            return reply
        self.flipped = True
        wrong = self.FLIPS[match.group(2).lower()]
        logging.getLogger("claims").info(
            "Fault injection: the model's draft %s was replaced with %s.", match.group(2), wrong
        )
        return reply[: match.start(2)] + wrong + reply[match.end(2) :]


def _run_one(sentence: str, path: Path, chat: ChatModel | None = None) -> str | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    model = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    path.write_text(f"{model}\n")
    os.environ["CLAIMS_LOG"] = str(path.resolve())
    claim_log = logging.getLogger("claims")
    claim_log.setLevel(logging.INFO)
    claim_log.propagate = False
    claim_log.handlers.clear()
    formatter = logging.Formatter("%(message)s")
    stream = logging.StreamHandler()
    record = logging.FileHandler(path, mode="a")
    stream.setFormatter(formatter)
    record.setFormatter(formatter)
    claim_log.addHandler(stream)
    claim_log.addHandler(record)
    try:
        for _event in run(sentence, chat):
            pass
    except RuntimeError as error:
        return str(error)
    finally:
        for handler in claim_log.handlers:
            handler.close()
        claim_log.handlers.clear()
    return None


if __name__ == "__main__":
    raise SystemExit(main())
