# Live Notebook Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add notebook-based control and monitoring for the live runner so `trade.ipynb` can configure strategies, start the runner, inspect status, read live logs, and stop the process safely.

**Architecture:** Keep `run_live.py` as the actual long-running process and `live_runner.py` as the loop implementation. Add `notebook_controls.py` as the notebook-safe subprocess and log-control layer, extend the runner to append CSV rows and PID/config files, and update `trade.ipynb` to become a live control panel.

**Tech Stack:** Python, pandas, subprocess, pathlib, json, pytest, Jupyter notebook JSON

---

## File Map

- Create: `notebook_controls.py`
- Modify: `live_runner.py`
- Modify: `run_live.py`
- Modify: `trade.ipynb`
- Modify: `tests/test_trade_notebook.py`
- Create: `tests/test_notebook_controls.py`

### Task 1: Add Live Log Writer To Runner

**Files:**
- Modify: `live_runner.py`
- Test: `tests/test_notebook_controls.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pandas as pd

from live_runner import append_live_runner_log


def test_append_live_runner_log_writes_csv_row(tmp_path: Path):
    log_path = tmp_path / "live_runner_log.csv"
    summary_df = pd.DataFrame(
        [
            {
                "symbol": "BTCUSD",
                "execution_status": "NO_ACTION",
                "signal": "BUY",
                "action": "DRY_RUN_BUY",
                "order_submitted": False,
            }
        ]
    )
    symbol_state = {
        "last_processed_bar_timestamp": "2026-04-25T12:00:00+00:00",
        "pyramid_count": 1,
    }

    append_live_runner_log(
        log_path=log_path,
        summary_df=summary_df,
        config={"timeframe": "5Min", "strategy": "rsi_mean_reversion_scalp"},
        symbol_state=symbol_state,
    )

    result = pd.read_csv(log_path)

    assert list(result["symbol"]) == ["BTCUSD"]
    assert list(result["strategy"]) == ["rsi_mean_reversion_scalp"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py::test_append_live_runner_log_writes_csv_row -v`
Expected: FAIL with missing function

- [ ] **Step 3: Write minimal implementation**

Add a helper to `live_runner.py` that:
- builds a one-row dict from `summary_df`
- appends `timestamp_utc`, `timeframe`, `strategy`, `last_processed_bar_timestamp`, `pyramid_count`
- writes/appends to CSV

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py::test_append_live_runner_log_writes_csv_row -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add live_runner.py tests/test_notebook_controls.py
git commit -m "Add live runner CSV logging"
```

### Task 2: Wire Runner Logging Into Live Loop

**Files:**
- Modify: `live_runner.py`
- Test: `tests/test_notebook_controls.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from live_runner import run_live_cycle


def test_run_live_cycle_appends_log_row_when_log_path_present(monkeypatch, tmp_path):
    log_path = tmp_path / "live_runner_log.csv"
    runtime_state = {
        "BTCUSD": {
            "last_processed_bar_timestamp": "",
            "last_signal": "",
            "last_action": "",
            "last_order_timestamp": "",
            "pyramid_count": 0,
        }
    }

    def fake_run_engine_bundle(config):
        return {
            "market_data_df": pd.DataFrame([{"timestamp": "2026-04-25T12:00:00+00:00"}]),
            "summary_df": pd.DataFrame([{"symbol": "BTCUSD", "execution_status": "NO_ACTION", "signal": "BUY", "action": "DRY_RUN_BUY", "order_submitted": False}]),
            "signal_df": pd.DataFrame([{"signal": "BUY", "action": "DRY_RUN_BUY"}]),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    run_live_cycle(
        {
            "symbols": ["BTCUSD"],
            "strategy": "rsi_mean_reversion_scalp",
            "timeframe": "5Min",
            "live_log_path": str(log_path),
        },
        runtime_state=runtime_state,
    )

    result = pd.read_csv(log_path)
    assert list(result["symbol"]) == ["BTCUSD"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py::test_run_live_cycle_appends_log_row_when_log_path_present -v`
Expected: FAIL because log writing is not connected yet

- [ ] **Step 3: Write minimal implementation**

Update `run_live_cycle()` to call `append_live_runner_log()` when `config` includes `live_log_path`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py::test_run_live_cycle_appends_log_row_when_log_path_present -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add live_runner.py tests/test_notebook_controls.py
git commit -m "Wire live log output into runner cycle"
```

### Task 3: Add Notebook Control Helpers

**Files:**
- Create: `notebook_controls.py`
- Test: `tests/test_notebook_controls.py`

- [ ] **Step 1: Write the failing tests**

```python
from notebook_controls import normalize_control_paths, read_live_log_df


def test_normalize_control_paths_returns_pid_config_and_log_paths():
    paths = normalize_control_paths()

    assert "pid_path" in paths
    assert "config_path" in paths
    assert "log_path" in paths


def test_read_live_log_df_returns_dataframe_for_existing_log(tmp_path):
    log_path = tmp_path / "live_runner_log.csv"
    log_path.write_text("timestamp_utc,symbol\\n2026-04-25T12:00:00+00:00,BTCUSD\\n")

    df = read_live_log_df(log_path=log_path)

    assert list(df["symbol"]) == ["BTCUSD"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py::test_normalize_control_paths_returns_pid_config_and_log_paths tests/test_notebook_controls.py::test_read_live_log_df_returns_dataframe_for_existing_log -v`
Expected: FAIL with missing module

- [ ] **Step 3: Write minimal implementation**

`notebook_controls.py` should add:
- `normalize_control_paths()`
- `read_live_log_df(log_path=None, tail_rows=None)`

with sensible defaults under `logs/`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py::test_normalize_control_paths_returns_pid_config_and_log_paths tests/test_notebook_controls.py::test_read_live_log_df_returns_dataframe_for_existing_log -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add notebook_controls.py tests/test_notebook_controls.py
git commit -m "Add notebook log-control helpers"
```

### Task 4: Add Start/Status/Stop Helpers

**Files:**
- Modify: `notebook_controls.py`
- Modify: `run_live.py`
- Test: `tests/test_notebook_controls.py`

- [ ] **Step 1: Write the failing tests**

```python
from notebook_controls import get_live_runner_status_df


def test_get_live_runner_status_df_reports_missing_pid_file(tmp_path):
    pid_path = tmp_path / "live_runner.pid"

    df = get_live_runner_status_df(pid_path=pid_path)

    assert bool(df.loc[0, "is_running"]) is False
    assert df.loc[0, "status"] == "NOT_RUNNING"
```

Also add tests for:
- duplicate runner start refusal when PID is active
- stop helper returning a DataFrame when PID file is missing or stale

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py -k "status or stop or start" -v`
Expected: FAIL with missing helpers

- [ ] **Step 3: Write minimal implementation**

Add to `notebook_controls.py`:
- `get_live_runner_status_df(...)`
- `start_live_runner(live_config, ...)`
- `stop_live_runner(...)`

Update `run_live.py` so it can:
- read config from a config JSON file path
- write PID file on startup

Keep the helpers DataFrame-first.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py -k "status or stop or start" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add notebook_controls.py run_live.py tests/test_notebook_controls.py
git commit -m "Add notebook live runner process controls"
```

### Task 5: Update Trade Notebook Into Live Control Panel

**Files:**
- Modify: `trade.ipynb`
- Modify: `tests/test_trade_notebook.py`

- [ ] **Step 1: Write the failing notebook test**

Add assertions to `tests/test_trade_notebook.py` for notebook control-panel cells containing:

```python
from notebook_controls import (
    get_live_runner_status_df,
    read_live_log_df,
    start_live_runner,
    stop_live_runner,
)
```

and code snippets for:
- `live_config =`
- `start_live_runner(live_config)`
- `get_live_runner_status_df()`
- `read_live_log_df(`
- `stop_live_runner()`

- [ ] **Step 2: Run notebook test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_trade_notebook.py::test_trade_notebook_has_engine_workflow_cells -v`
Expected: FAIL because notebook does not yet contain the control cells

- [ ] **Step 3: Update notebook**

Revise `trade.ipynb` so it includes:
- one-shot engine config and inspection
- live config cell with strategy/strategy_params/risk_params
- start cell
- status cell
- live logs cell
- stop cell

Keep the notebook JSON clean and without stale outputs.

- [ ] **Step 4: Run notebook test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_trade_notebook.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add trade.ipynb tests/test_trade_notebook.py
git commit -m "Turn trade notebook into live runner control panel"
```

### Task 6: Run Full Verification

**Files:**
- Modify: `tests/test_notebook_controls.py`
- Modify: `tests/test_trade_notebook.py`

- [ ] **Step 1: Run notebook-control tests**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_notebook_controls.py -v`
Expected: PASS

- [ ] **Step 2: Run notebook tests**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/test_trade_notebook.py -v`
Expected: PASS

- [ ] **Step 3: Run full suite**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests -v`
Expected: PASS

- [ ] **Step 4: Commit final verified implementation**

```bash
git add notebook_controls.py live_runner.py run_live.py trade.ipynb tests/test_notebook_controls.py tests/test_trade_notebook.py
git commit -m "Add notebook controls for live runner monitoring"
```

## Self-Review

- Spec coverage:
  - notebook start/stop control: Task 4, Task 5
  - log viewing: Task 1, Task 2, Task 3, Task 5
  - strategy selection/config from notebook: Task 5
  - PID/config/log file handling: Task 3, Task 4
- Placeholder scan:
  - no placeholders remain
- Type consistency:
  - DataFrame-first helper contract is consistent
  - log path / pid path / config path naming is consistent across tasks
