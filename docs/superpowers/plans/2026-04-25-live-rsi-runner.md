# Live RSI Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular live Alpaca RSI runner that processes configured symbols sequentially, trades long-only with pyramiding, fully closes on exit, and avoids duplicate in-progress-bar orders.

**Architecture:** The existing engine remains a one-symbol execution unit. New runtime modules add capability profiles, in-memory symbol state, pyramiding-aware risk checks, and a sequential polling loop that builds symbol-specific configs and calls the engine repeatedly.

**Tech Stack:** Python, pandas, alpaca-py, pytest

---

## File Map

- Create: `capabilities.py`
- Create: `runtime_state.py`
- Create: `live_runner.py`
- Create: `run_live.py`
- Modify: `registry.py`
- Modify: `engine.py`
- Modify: `execution.py`
- Modify: `risk/basic_rules.py`
- Modify: `tests/test_modular_engine.py`
- Create: `tests/test_live_runner.py`

### Task 1: Add Capability Profiles

**Files:**
- Create: `capabilities.py`
- Test: `tests/test_live_runner.py`

- [ ] **Step 1: Write the failing test**

```python
from capabilities import CAPABILITY_PROFILES


def test_alpaca_crypto_long_only_profile_exists():
    profile = CAPABILITY_PROFILES["alpaca_crypto_long_only"]

    assert profile["supports_long"] is True
    assert profile["supports_short"] is False
    assert profile["supports_fractional"] is True
    assert profile["supports_pyramiding"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_runner.py::test_alpaca_crypto_long_only_profile_exists -v`
Expected: FAIL with `ModuleNotFoundError` or missing profile

- [ ] **Step 3: Write minimal implementation**

```python
CAPABILITY_PROFILES = {
    "alpaca_crypto_long_only": {
        "name": "alpaca_crypto_long_only",
        "supports_long": True,
        "supports_short": False,
        "supports_fractional": True,
        "supports_pyramiding": True,
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_runner.py::test_alpaca_crypto_long_only_profile_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add capabilities.py tests/test_live_runner.py
git commit -m "Add live trading capability profiles"
```

### Task 2: Add Runtime State Helpers

**Files:**
- Create: `runtime_state.py`
- Test: `tests/test_live_runner.py`

- [ ] **Step 1: Write the failing test**

```python
from runtime_state import build_initial_state, should_suppress_duplicate_action


def test_build_initial_state_creates_symbol_state():
    state = build_initial_state(["BTCUSD", "ETHUSD"])

    assert state["BTCUSD"]["pyramid_count"] == 0
    assert state["BTCUSD"]["last_processed_bar_timestamp"] == ""
    assert state["ETHUSD"]["last_action"] == ""


def test_should_suppress_duplicate_action_returns_true_for_same_bar_and_action():
    symbol_state = {
        "last_processed_bar_timestamp": "2026-04-25T12:00:00+00:00",
        "last_action": "BUY",
        "last_order_timestamp": "2026-04-25T12:00:10+00:00",
        "pyramid_count": 1,
    }

    assert should_suppress_duplicate_action(
        symbol_state=symbol_state,
        current_bar_timestamp="2026-04-25T12:00:00+00:00",
        current_action="BUY",
    ) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_runner.py::test_build_initial_state_creates_symbol_state tests/test_live_runner.py::test_should_suppress_duplicate_action_returns_true_for_same_bar_and_action -v`
Expected: FAIL with missing module or missing functions

- [ ] **Step 3: Write minimal implementation**

```python
def build_initial_state(symbols: list[str]) -> dict[str, dict]:
    return {
        symbol: {
            "last_processed_bar_timestamp": "",
            "last_signal": "",
            "last_action": "",
            "last_order_timestamp": "",
            "pyramid_count": 0,
        }
        for symbol in symbols
    }


def should_suppress_duplicate_action(symbol_state: dict, current_bar_timestamp: str, current_action: str) -> bool:
    return (
        symbol_state.get("last_processed_bar_timestamp", "") == current_bar_timestamp
        and symbol_state.get("last_action", "") == current_action
        and current_action != ""
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_runner.py::test_build_initial_state_creates_symbol_state tests/test_live_runner.py::test_should_suppress_duplicate_action_returns_true_for_same_bar_and_action -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add runtime_state.py tests/test_live_runner.py
git commit -m "Add live runtime state helpers"
```

### Task 3: Add Pyramiding Risk Rule

**Files:**
- Modify: `risk/basic_rules.py`
- Test: `tests/test_live_runner.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from risk import RISK_RULE_REGISTRY


def test_pyramiding_limit_blocks_when_max_pyramids_reached():
    signal_df = pd.DataFrame([{"symbol": "BTCUSD", "signal": "BUY", "should_submit_order": True}])
    positions_df = pd.DataFrame([{"symbol": "BTC/USD", "qty": 0.003}])
    orders_df = pd.DataFrame()
    config = {
        "symbol": "BTCUSD",
        "qty": 0.001,
        "runtime_state": {"BTCUSD": {"pyramid_count": 3, "last_order_timestamp": "", "last_processed_bar_timestamp": "", "last_action": ""}},
        "risk_params": {
            "max_position_qty": 0.005,
            "max_pyramids": 3,
            "pyramid_cooldown_seconds": 60,
        },
    }

    result = RISK_RULE_REGISTRY["pyramiding_limit"](signal_df, positions_df, orders_df, config)

    assert result.iloc[0]["ok"] is False
    assert result.iloc[0]["reason"] == "MAX_PYRAMIDS_REACHED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_runner.py::test_pyramiding_limit_blocks_when_max_pyramids_reached -v`
Expected: FAIL with missing rule

- [ ] **Step 3: Write minimal implementation**

```python
@register_risk_rule("pyramiding_limit")
def pyramiding_limit_rule(signal_df: pd.DataFrame, positions_df: pd.DataFrame, orders_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    signal = signal_df.iloc[0].get("signal", "DO_NOTHING")
    symbol = config.get("symbol", "")
    if signal != "BUY":
        return pd.DataFrame([{"rule_name": "pyramiding_limit", "ok": True, "reason": "NOT_APPLICABLE", "symbol": symbol}])

    runtime_state = config.get("runtime_state", {}).get(symbol, {})
    risk_params = config.get("risk_params", {})
    max_pyramids = int(risk_params.get("max_pyramids", 0))
    current_pyramids = int(runtime_state.get("pyramid_count", 0))

    if current_pyramids >= max_pyramids:
        return pd.DataFrame([{"rule_name": "pyramiding_limit", "ok": False, "reason": "MAX_PYRAMIDS_REACHED", "symbol": symbol}])

    return pd.DataFrame([{"rule_name": "pyramiding_limit", "ok": True, "reason": "OK", "symbol": symbol}])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_runner.py::test_pyramiding_limit_blocks_when_max_pyramids_reached -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add risk/basic_rules.py tests/test_live_runner.py
git commit -m "Add pyramiding risk rule"
```

### Task 4: Add Live Preset

**Files:**
- Modify: `registry.py`
- Test: `tests/test_modular_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from registry import resolve_engine_config


def test_live_rsi_preset_resolves_expected_defaults():
    config = resolve_engine_config({"preset": "alpaca_rsi_scalp_live"})

    assert config["strategy"] == "rsi_mean_reversion_scalp"
    assert config["timeframe"] == "5Min"
    assert config["poll_interval_seconds"] == 30
    assert config["capability_profile"] == "alpaca_crypto_long_only"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_modular_engine.py::test_live_rsi_preset_resolves_expected_defaults -v`
Expected: FAIL with `KeyError`

- [ ] **Step 3: Write minimal implementation**

```python
"alpaca_rsi_scalp_live": {
    "market_data_provider": "alpaca",
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
    "risk_rules": ["max_position", "pyramiding_limit"],
    "risk_params": {
        "max_position_qty": 0.005,
        "max_pyramids": 3,
        "pyramid_cooldown_seconds": 60,
    },
    "execution_handler": "alpaca_paper",
    "capability_profile": "alpaca_crypto_long_only",
    "symbols": ["BTCUSD"],
    "timeframe": "5Min",
    "lookback_days": 7,
    "qty": 0.001,
    "submit_orders": False,
    "poll_interval_seconds": 30,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_modular_engine.py::test_live_rsi_preset_resolves_expected_defaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add registry.py tests/test_modular_engine.py
git commit -m "Add live RSI preset"
```

### Task 5: Extend Execution For Long-Only Live Behavior

**Files:**
- Modify: `execution.py`
- Test: `tests/test_live_runner.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from execution import alpaca_paper_execution_handler


def test_execution_handler_blocks_short_signal_for_long_only_profile():
    signal_df = pd.DataFrame([{"signal": "SELL_SHORT", "action": "RSI_CROSSED_BACK_BELOW_OVERBOUGHT", "should_submit_order": True}])
    config = {
        "symbol": "BTCUSD",
        "submit_orders": True,
        "capability_profile": "alpaca_crypto_long_only",
    }

    result = alpaca_paper_execution_handler(signal_df, config)

    assert result.iloc[0]["status"] == "UNSUPPORTED_ACTION"
    assert result.iloc[0]["order_submitted"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_runner.py::test_execution_handler_blocks_short_signal_for_long_only_profile -v`
Expected: FAIL because current handler only understands BUY/no-op

- [ ] **Step 3: Write minimal implementation**

```python
from capabilities import CAPABILITY_PROFILES


profile_name = config.get("capability_profile", "")
profile = CAPABILITY_PROFILES.get(profile_name, {})
signal = signal_df.iloc[0].get("signal", "DO_NOTHING")

if signal in {"SELL_SHORT", "BUY_TO_COVER"} and not profile.get("supports_short", False):
    return pd.DataFrame(
        [
            {
                "ok": False,
                "order_submitted": False,
                "order_id": "",
                "status": "UNSUPPORTED_ACTION",
                "symbol": config["symbol"],
                "action": signal,
            }
        ]
    )
```

Also extend the handler to:

- submit `BUY` as before
- map `SELL` to a full-close path
- keep dry-run behavior for both

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_runner.py::test_execution_handler_blocks_short_signal_for_long_only_profile -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add execution.py tests/test_live_runner.py
git commit -m "Extend live execution for long-only profiles"
```

### Task 6: Add Symbol-Aware Engine Entry Point For Live Use

**Files:**
- Modify: `engine.py`
- Test: `tests/test_live_runner.py`

- [ ] **Step 1: Write the failing test**

```python
from engine import build_symbol_config


def test_build_symbol_config_overrides_symbol_without_mutating_base_config():
    config = {"symbols": ["BTCUSD", "ETHUSD"], "symbol": "SPY", "qty": 0.001}

    symbol_config = build_symbol_config(config, "ETHUSD")

    assert symbol_config["symbol"] == "ETHUSD"
    assert config["symbol"] == "SPY"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_runner.py::test_build_symbol_config_overrides_symbol_without_mutating_base_config -v`
Expected: FAIL because helper does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def build_symbol_config(config: dict, symbol: str) -> dict:
    symbol_config = dict(config)
    symbol_config["symbol"] = symbol
    return symbol_config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_runner.py::test_build_symbol_config_overrides_symbol_without_mutating_base_config -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine.py tests/test_live_runner.py
git commit -m "Add symbol config helper for live runner"
```

### Task 7: Add Sequential Live Runner

**Files:**
- Create: `live_runner.py`
- Test: `tests/test_live_runner.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from live_runner import run_live_cycle


def test_run_live_cycle_returns_one_row_per_symbol(monkeypatch):
    def fake_run_engine_bundle(config):
        return {
            "summary_df": pd.DataFrame([{"symbol": config["symbol"], "execution_status": "NO_ACTION"}]),
            "signal_df": pd.DataFrame([{"signal": "DO_NOTHING", "action": "NO_SIGNAL"}]),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    result = run_live_cycle(
        {
            "symbols": ["BTCUSD", "ETHUSD"],
        },
        runtime_state={
            "BTCUSD": {"last_processed_bar_timestamp": "", "last_signal": "", "last_action": "", "last_order_timestamp": "", "pyramid_count": 0},
            "ETHUSD": {"last_processed_bar_timestamp": "", "last_signal": "", "last_action": "", "last_order_timestamp": "", "pyramid_count": 0},
        },
    )

    assert list(result["symbol"]) == ["BTCUSD", "ETHUSD"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_runner.py::test_run_live_cycle_returns_one_row_per_symbol -v`
Expected: FAIL with missing module or function

- [ ] **Step 3: Write minimal implementation**

```python
import pandas as pd

from engine import build_symbol_config, run_engine_bundle


def run_live_cycle(config: dict, runtime_state: dict) -> pd.DataFrame:
    rows = []
    for symbol in config.get("symbols", []):
        symbol_config = build_symbol_config(config, symbol)
        symbol_config["runtime_state"] = runtime_state
        bundle = run_engine_bundle(symbol_config)
        summary_df = bundle.get("summary_df", pd.DataFrame())
        if summary_df.empty:
            rows.append({"symbol": symbol, "execution_status": "NO_SUMMARY"})
        else:
            rows.append(summary_df.iloc[0].to_dict())
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_runner.py::test_run_live_cycle_returns_one_row_per_symbol -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add live_runner.py tests/test_live_runner.py
git commit -m "Add sequential live cycle runner"
```

### Task 8: Add Duplicate Suppression And State Updates

**Files:**
- Modify: `live_runner.py`
- Modify: `runtime_state.py`
- Test: `tests/test_live_runner.py`

- [ ] **Step 1: Write the failing test**

```python
from runtime_state import update_symbol_state


def test_update_symbol_state_tracks_processed_bar_and_action():
    symbol_state = {
        "last_processed_bar_timestamp": "",
        "last_signal": "",
        "last_action": "",
        "last_order_timestamp": "",
        "pyramid_count": 0,
    }

    updated = update_symbol_state(
        symbol_state,
        current_bar_timestamp="2026-04-25T12:00:00+00:00",
        current_signal="BUY",
        current_action="BUY",
        order_submitted=True,
        pyramid_increment=1,
    )

    assert updated["last_processed_bar_timestamp"] == "2026-04-25T12:00:00+00:00"
    assert updated["last_action"] == "BUY"
    assert updated["pyramid_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_runner.py::test_update_symbol_state_tracks_processed_bar_and_action -v`
Expected: FAIL because helper does not exist

- [ ] **Step 3: Write minimal implementation**

```python
from datetime import datetime, timezone


def update_symbol_state(symbol_state: dict, current_bar_timestamp: str, current_signal: str, current_action: str, order_submitted: bool, pyramid_increment: int) -> dict:
    updated = dict(symbol_state)
    updated["last_processed_bar_timestamp"] = current_bar_timestamp
    updated["last_signal"] = current_signal
    updated["last_action"] = current_action
    if order_submitted:
        updated["last_order_timestamp"] = datetime.now(timezone.utc).isoformat()
    updated["pyramid_count"] = int(updated.get("pyramid_count", 0)) + int(pyramid_increment)
    return updated
```

Then update `live_runner.py` to call it after each symbol cycle.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_runner.py::test_update_symbol_state_tracks_processed_bar_and_action -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add live_runner.py runtime_state.py tests/test_live_runner.py
git commit -m "Track live runner symbol state"
```

### Task 9: Add Continuous Runner And CLI Entry Point

**Files:**
- Create: `run_live.py`
- Modify: `live_runner.py`
- Test: `tests/test_live_runner.py`

- [ ] **Step 1: Write the failing test**

```python
from live_runner import normalize_live_symbols


def test_normalize_live_symbols_uses_symbols_field_when_present():
    result = normalize_live_symbols({"symbols": ["BTCUSD", "ETHUSD"]})

    assert result == ["BTCUSD", "ETHUSD"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_runner.py::test_normalize_live_symbols_uses_symbols_field_when_present -v`
Expected: FAIL because helper does not exist

- [ ] **Step 3: Write minimal implementation**

```python
import time

from registry import resolve_engine_config
from runtime_state import build_initial_state


def normalize_live_symbols(config: dict) -> list[str]:
    if config.get("symbols"):
        return list(config["symbols"])
    if config.get("symbol"):
        return [config["symbol"]]
    return []


def run_live_loop(config: dict):
    resolved = resolve_engine_config(config)
    symbols = normalize_live_symbols(resolved)
    runtime_state = build_initial_state(symbols)
    while True:
        run_live_cycle(resolved, runtime_state)
        time.sleep(int(resolved.get("poll_interval_seconds", 30)))
```

And add `run_live.py`:

```python
from live_runner import run_live_loop


if __name__ == "__main__":
    run_live_loop({"preset": "alpaca_rsi_scalp_live", "submit_orders": True})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_runner.py::test_normalize_live_symbols_uses_symbols_field_when_present -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add live_runner.py run_live.py tests/test_live_runner.py
git commit -m "Add continuous live runner entry point"
```

### Task 10: Run Focused And Full Verification

**Files:**
- Modify: `tests/test_modular_engine.py`
- Create/Modify: `tests/test_live_runner.py`

- [ ] **Step 1: Run focused live-runner tests**

Run: `pytest tests/test_live_runner.py -v`
Expected: PASS

- [ ] **Step 2: Run modular engine tests**

Run: `pytest tests/test_modular_engine.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests -v`
Expected: PASS

- [ ] **Step 4: Commit final verification-safe implementation**

```bash
git add capabilities.py runtime_state.py live_runner.py run_live.py registry.py engine.py execution.py risk/basic_rules.py tests/test_modular_engine.py tests/test_live_runner.py
git commit -m "Implement live RSI runner for Alpaca"
```

## Self-Review

- Spec coverage:
  - multi-symbol sequential runner: Task 7, Task 9
  - long-only capability profile: Task 1, Task 5
  - pyramiding caps: Task 3
  - full-close exit path: Task 5
  - duplicate suppression/runtime state: Task 2, Task 8
  - live preset: Task 4
  - stable modular engine integration: Task 6
- Placeholder scan:
  - no `TBD` or deferred implementation notes remain
- Type consistency:
  - `runtime_state` shape is defined consistently across tasks
  - `capability_profile`, `poll_interval_seconds`, and `symbols` naming matches the spec
