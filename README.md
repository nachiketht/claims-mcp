# claims-mcp

An MCP server for equipment requests. It looks up an employee and that role's refresh intervals. The decision date is the day you run it.

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

`python demo.py E1001` runs one request. The five transcripts are written under `evidence/`. If the model cannot be reached, the command prints `cannot reach the model at host.docker.internal:11434` and writes no approval.

Ask a custom question with the employee id in the sentence. The trace prints in the terminal and is not saved under `evidence/`. The latency line is model time, tool time, and total time.

```bash
python ask.py "E1002 needs a monitor because the current one is broken."
```

## 6. Open the browser demo

```bash
uvicorn web:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. The five demo sentences are buttons. A text box sends any other sentence. The page streams the same trace, then shows the decision, the latency line, and the review records.

## 7. Run the tests in CI

`.github/workflows/ci.yml` runs `pytest` on Python 3.12 for every push to `main`. Actions does not call Ollama. The local passing list is `evidence/10-pytest.txt`.
