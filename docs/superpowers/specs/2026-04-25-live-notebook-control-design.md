# Live Notebook Control Design

## Goal

Turn `trade.ipynb` into a live control panel that can:

- configure the live runner
- select strategies and strategy parameters
- start the live runner
- monitor live cycle logs
- stop the live runner

while keeping the actual always-on trading loop outside the notebook.

## Why

The current system now supports:

- a modular one-shot engine
- a modular live runner loop
- long-only Alpaca-compatible live behavior
- strategy/risk/execution configuration through registries

What is missing is an operator-friendly workflow in the notebook. The notebook should act as the command center, while the live process remains a normal Python process that can keep running until stopped.

## Design Principle

The notebook should control the runner, not become the runner.

That means:

- `run_live.py` remains the long-running process
- `live_runner.py` remains the loop implementation
- the notebook interacts through small helper functions and log files

This avoids fragile infinite-loop notebook cells while still giving the user live visibility and control.

## Scope

This design covers:

- starting the live runner from `trade.ipynb`
- stopping the live runner from `trade.ipynb`
- checking whether the runner is active
- showing recent live cycle logs in DataFrame form
- making strategy choice and params notebook-configurable

This design does not cover:

- embedding the infinite loop directly in notebook cells
- websocket dashboards
- multi-process orchestration
- database-backed persistent runtime state

## Architecture

### Components

- `live_runner.py`
  Keeps its role as the continuous sequential trading loop, and now appends one structured row per symbol-cycle to a CSV log.

- `run_live.py`
  Remains the process entry point, but should support notebook-driven startup via a config file or equivalent handoff and manage a PID file.

- `notebook_controls.py`
  New helper module for notebook-safe control:
  - start the live runner subprocess
  - check process status
  - stop the live runner
  - load live log rows into a pandas DataFrame

- `trade.ipynb`
  Becomes the live control panel.

## Notebook Config Contract

The notebook should define one config object that controls both one-shot inspection and live runner behavior.

Example:

```python
live_config = {
    "preset": "alpaca_rsi_scalp_live",
    "symbols": ["BTCUSD"],
    "strategy": "rsi_mean_reversion_scalp",
    "strategy_params": {
        "rsi_window": 5,
        "oversold_threshold": 30,
        "overbought_threshold": 70,
        "exit_threshold": 50,
        "short_exit_threshold": 50,
        "stop_loss_pct": 0.004,
        "take_profit_pct": 0.006,
    },
    "risk_params": {
        "max_position_qty": 0.005,
        "max_pyramids": 3,
        "pyramid_cooldown_seconds": 60,
    },
    "poll_interval_seconds": 30,
    "submit_orders": True,
}
```

The important point is that `trade.ipynb` should be able to change:

- strategy name
- strategy parameters
- symbol list
- risk parameters
- polling interval
- whether paper orders are actually submitted

without editing the runner code.

## Live Log Schema

Use one CSV row per symbol-cycle, appended under `logs/live_runner_log.csv`.

Recommended columns:

- `timestamp_utc`
- `symbol`
- `timeframe`
- `strategy`
- `signal`
- `action`
- `execution_status`
- `order_submitted`
- `last_processed_bar_timestamp`
- `pyramid_count`

This is intentionally simple and notebook-friendly. It supports:

- recent activity inspection
- symbol filtering
- debugging repeated signals
- seeing whether cycles actually submitted orders

## PID File

Use:

- `logs/live_runner.pid`

When the runner starts, it writes its process ID there.

The notebook helper should use the PID file to:

- detect whether a runner is active
- avoid starting duplicate runner processes
- stop the running process cleanly

If the PID file exists but the process is gone, the notebook should report a stale PID state and allow cleanup.

## Notebook Workflow

### 1. Config Cell

The notebook defines a single `live_config` dict.

### 2. Start Cell

Calls a helper like:

```python
start_live_runner(live_config)
```

This should:

- refuse to start if another runner is already active
- write config handoff data for the subprocess
- launch `run_live.py`
- write the PID file
- return a status DataFrame

### 3. Status Cell

Calls a helper like:

```python
get_live_runner_status_df()
```

This should show:

- whether the runner is active
- the PID if active
- PID file path
- log file path

### 4. Logs Cell

Calls:

```python
read_live_log_df(tail_rows=100)
```

This should return a DataFrame ready for display in the notebook.

### 5. Stop Cell

Calls:

```python
stop_live_runner()
```

This should:

- read the PID file
- terminate the running process
- return a status DataFrame

## Start/Stop Mechanics

The notebook should launch the runner as a background subprocess.

Recommended flow:

1. Write the current notebook config to a file in `logs/`, such as `logs/live_runner_config.json`
2. Launch `run_live.py` in a background subprocess
3. `run_live.py` loads the config file, starts the loop, and writes `logs/live_runner.pid`
4. The notebook can later inspect or stop the process using that PID

This is simpler and more stable than trying to serialize the whole config on the command line.

## Safety Rules

- do not start a second runner if one is already active
- append to logs instead of overwriting them
- tolerate stale PID files
- keep monitor functions notebook-friendly and DataFrame-first
- keep the live loop outside the notebook itself

## File Changes

### New

- `notebook_controls.py`

### Modified

- `live_runner.py`
- `run_live.py`
- `trade.ipynb`

## Testing Strategy

Add tests for:

- symbol normalization / config handoff where applicable
- start helper refusing duplicate active runner
- status helper handling missing and stale PID files
- stop helper handling active and inactive states
- live log loader returning a DataFrame from the CSV log

Notebook structure tests should also be updated to reflect the new control-panel cells.

## Success Criteria

This feature is successful when:

- the notebook can start the live runner
- the notebook can confirm whether the runner is active
- the notebook can stop the live runner
- the notebook can read live logs into a DataFrame
- the notebook can configure strategy name and strategy params without code edits
- the always-on trading loop still lives outside notebook cells
