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
