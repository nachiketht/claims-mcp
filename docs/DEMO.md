# Demo notes

## 1. The job

An employee asks for equipment. The system looks up that person and that role's refresh rule, then approves a clear eligible request, denies a clear ineligible request, or hands an ambiguous case to a person.

## 2. The five people

E1001 is an engineer with no monitor on file, so a monitor is eligible. E1002 is a manager whose laptop was issued on 2025-06-15, still inside 24 months. E1003 is an engineer whose laptop is old enough to refresh, and the sentence says it was stolen. E1004 is an engineer asking for a drawing tablet, which is not in the policy. E1005 is the CEO, whose laptop was issued on 2025-01-10 and a newer laptop launched on 2026-03-01.

## 3. The picture

The records live in `data.py` and are read through `MemoryCatalog`. Four tools sit on the MCP server: employee info, policy limits, eligibility, and the review flag. The agent in `agent.py` chooses the tool. The model runs on the laptop outside the container, through `OllamaChat`. A new model, a new connection, a new record source, or a new review inbox is a new class passed in, and the rules stay put.

## 4. What the room will see

Open `http://localhost:8000`. Click a request. Each Thought, Action, and Observation appears as it happens. The latency line gives model time, tool time, and total time for that run. Then read the decision and the review list.

The graded terminal evidence is these two commands. The log lines on screen are the trace of that request.

```bash
pytest -v
python demo.py E1001
```

## 5. Spoken lines

- E1001 needs a monitor. First monitor is eligible.
- E1002 wants a new laptop because the current one is slow. Manager laptop from June 2025 is ineligible.
- E1003 says the laptop was stolen. Stolen laptop finishes only after a review record.
- E1004 needs a drawing tablet. Drawing tablet is undetermined.
- E1005 needs a new laptop because a new one launched. CEO laptop is eligible after a new model launched.

Extra recorded scenarios (`python demo.py ceo-monitor broken lost pumpkin unknown`):

- E1005 needs a new monitor. Denied: no newer monitor has launched.
- E1002 says the monitor is broken. Escalated; the guardrail line shows the agent recorded the review when the model did not.
- E1004 lost the laptop on a trip. Escalated, even though the schedule says ineligible.
- E1005 wants pumpkin spice. Escalated: not in the policy, even for the CEO.
- E9999 needs a laptop. No decision and no review record.

## 6. What the system leaves to a person

A stolen, lost, or broken device is not a scheduled refresh, so the agent must flag it. An item the policy table does not list is undetermined, and a person decides. Every review reason names the trigger and the eligibility result.

## 7. Where reflection shows up

Each approval or denial prints `Draft`, `Reflection`, and `Reflection result`. In `evidence/06-deny-laptop.txt` the draft was `ineligible`, which is not a decision, and reflection changed it to `denied`. In `evidence/05`, `09`, and `12` reflection confirms the draft.
