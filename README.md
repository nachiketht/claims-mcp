# claims-mcp

An MCP server and ReAct agent for equipment requests. The server looks up an employee and that role's refresh intervals. The agent approves, denies, or escalates each request, and reflects on its draft before the decision is final. Every decision uses the day you run it. The unit tests pass a fixed date to the tools so their expected results do not change as the calendar moves.

Run these commands from the repository root.

## 1. Create the environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Run the tests

```bash
pytest -v
```

## 3. Check the one-tool connection

`minimal_client.py` starts `minimal_server.py` and calls `ding`.

```bash
python minimal_client.py
```

```text
initialize: claims
tools: ['ding']
ding: dong
```

## 4. Call the equipment tools

`client.py` starts `server.py`. It asks for employee `E1001`, the `manager` intervals, `E1001`'s monitor, `E1002`'s laptop, and a review flag for `E1003`'s stolen laptop.

```bash
python client.py
```

`E1001` comes back as an engineer, with tenure in whole months through today and a laptop issued on 2022-08-01. A manager may refresh a laptop every 24 months and a monitor every 36. `E1001`'s monitor is eligible because none is on file. `E1002`'s laptop is ineligible while 2025-06-15 is inside 24 months. The stolen-laptop flag writes one review record, and a second run returns that same record.

## 5. Run the live demo

Ollama must be running on the host at `0.0.0.0:11434` with `qwen3:8b` pulled. From this container:

```bash
export OLLAMA_HOST=http://host.docker.internal:11434
python demo.py
```

`python demo.py E1001` runs one request. Each transcript is written under `evidence/`. If the model cannot be reached, the command prints `cannot reach the model qwen3:8b at http://host.docker.internal:11434` and writes no approval. A model error (such as a model that is not pulled) or an MCP server that does not start or stops answering is printed the same way.

These are the recorded runs with `qwen3:8b`. The first line of each transcript names the model and the decision date, which was the day it ran (2026-10-02). A later run can differ where a refresh window has since elapsed: E1002's laptop, for example, becomes eligible on 2027-06-15.

| Key | Request | Scenario | Decision | Transcript |
| --- | --- | --- | --- | --- |
| `E1001` | E1001 needs a monitor. | No monitor on file | approved | `evidence/05-approve-monitor.txt` |
| `E1005` | E1005 needs a new laptop because a new one launched. | CEO: 12 months passed and a newer model launched | approved | `evidence/09-approve-ceo-laptop.txt` |
| `E1002` | E1002 wants a new laptop because the current one is slow. | Inside the manager's 24-month interval | denied | `evidence/06-deny-laptop.txt` |
| `ceo-monitor` | E1005 needs a new monitor. | CEO: no newer monitor has launched | denied | `evidence/12-deny-ceo-monitor.txt` |
| `E1003` | E1003 says the laptop was stolen. | Stolen, though the refresh schedule says eligible; the model flags it, and a guardrail line notes the review reason was rebuilt from the observations | escalated | `evidence/07-escalate-stolen.txt` |
| `broken` | E1002 says the monitor is broken. | Broken, though the refresh schedule says ineligible | escalated | `evidence/13-escalate-broken-monitor.txt` |
| `lost` | E1004 lost the laptop on a trip. | Lost, though the refresh schedule says ineligible | escalated | `evidence/14-escalate-lost-laptop.txt` |
| `E1004` | E1004 needs a drawing tablet. | Item not in the policy (undetermined) | escalated | `evidence/08-escalate-tablet.txt` |
| `pumpkin` | E1005 wants pumpkin spice. | The CEO's request for an item not in the policy | escalated | `evidence/15-escalate-ceo-pumpkin-spice.txt` |
| `unknown` | E9999 needs a laptop. | Unknown employee: no decision and no review | none | `evidence/16-unknown-employee.txt` |
| `reflection-fix` | E1002 wants a new laptop because the current one is slow. | Fault injection: the model's draft is flipped to approved, and reflection changes it back | denied | `evidence/17-reflection-corrects-draft.txt` |

Every approval, denial, and escalation prints `Draft`, `Reflection`, and `Reflection result`. In eight of the runs without fault injection, reflection confirms the model's draft. In `evidence/07` the model gave no final answer, so reflection reads the filed review and says `escalated`. The unknown-employee run stops before a draft. `reflection-fix` wraps the model in `FlipFirstDraft`, which swaps its first `Final Answer` to the opposite word, so the live reflection has a wrong draft to catch. The trace marks that swap with a `Fault injection` line.

The five review records these runs write are in `data/review_queue.json`. Each reason names the trigger and the eligibility result, then adds the model's own reason as `Model note`.

Ask a custom question with the employee id in the sentence. The trace prints in the terminal and is not saved under `evidence/`. The latency line is model time, tool time, and total time.

```bash
python ask.py "E1002 needs a monitor because the current one is broken."
```

## 6. Open the browser demo

```bash
uvicorn web:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. The ten recorded sentences are buttons. A text box sends any other sentence. The page streams the same trace, then shows the decision, the latency line, and the review records.

## 7. Run the tests in CI

`.github/workflows/ci.yml` runs `pytest -v` on Python 3.12 for every push to `main` and every pull request. Actions does not call Ollama. `test_server.py` starts `server.py` over stdio and calls all four tools. The local passing list is `evidence/10-pytest.txt`.
