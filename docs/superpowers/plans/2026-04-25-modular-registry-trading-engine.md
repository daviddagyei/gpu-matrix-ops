# Modular Registry Trading Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the current trading engine into a registry-driven modular architecture while preserving the existing notebook API and DataFrame outputs.

**Architecture:** Introduce focused modules for market data, strategies, risk, execution, registry resolution, and orchestration. Keep `alpaca_engine.py` as a compatibility layer so the notebook can continue importing the same functions while the new modular engine becomes the implementation backbone.

**Tech Stack:** Python, pandas, alpaca-py, python-dotenv, pytest

---

## File Responsibilities

- `market_data.py`
  Symbol normalization, asset routing, timeframe handling, and market-data provider registry implementation.

- `strategies/__init__.py`
  Strategy registry and registration helpers.

- `strategies/sma_trend.py`
  Default SMA strategy implementation.

- `risk/__init__.py`
  Risk registry and registration helpers.

- `risk/basic_rules.py`
  Default risk rules.

- `execution.py`
  Execution handler registry and Alpaca paper execution helpers.

- `registry.py`
  Preset definitions and config resolution.

- `engine.py`
  Orchestrator returning a notebook-friendly bundle of DataFrames.

- `alpaca_engine.py`
  Compatibility facade and notebook-facing wrappers.

- `tests/test_modular_engine.py`
  Unit tests for registry resolution, config overrides, strategy/risk pipeline, and bundle outputs.

### Task 1: Add failing tests for registry resolution and bundle structure

**Files:**
- Create: `tests/test_modular_engine.py`
- Test: `tests/test_modular_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from registry import resolve_engine_config
from engine import run_engine_bundle


def test_resolve_engine_config_applies_preset_and_overrides():
    config = resolve_engine_config(
        {
            "preset": "alpaca_sma_default",
            "symbol": "BTCUSD",
            "timeframe": "1Hour",
        }
    )

    assert config["symbol"] == "BTCUSD"
    assert config["timeframe"] == "1Hour"
    assert config["strategy"] == "sma_trend"


def test_run_engine_bundle_returns_expected_bundle_keys(monkeypatch):
    bundle = run_engine_bundle(
        {
            "preset": "alpaca_sma_default",
            "symbol": "SPY",
            "submit_orders": False,
        }
    )

    assert set(bundle) >= {
        "settings_df",
        "market_data_df",
        "signal_df",
        "risk_df",
        "execution_df",
        "positions_df",
        "orders_df",
        "summary_df",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_modular_engine.py -v`
Expected: FAIL with `ModuleNotFoundError` for `registry` or `engine`.

- [ ] **Step 3: Write minimal implementation**

Create the new modules with enough structure to define the preset resolver and a placeholder bundle runner that returns the expected keys as DataFrames.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_modular_engine.py -v`
Expected: PASS for both tests.

### Task 2: Add failing tests for strategy and risk registries

**Files:**
- Modify: `tests/test_modular_engine.py`
- Test: `tests/test_modular_engine.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from strategies import STRATEGY_REGISTRY
from risk import RISK_RULE_REGISTRY


def test_sma_trend_strategy_is_registered():
    assert "sma_trend" in STRATEGY_REGISTRY


def test_no_duplicate_entry_rule_blocks_existing_position():
    signal_df = pd.DataFrame([{"symbol": "SPY", "signal": "BUY", "action": "BUY"}])
    positions_df = pd.DataFrame([{"symbol": "SPY", "qty": "1"}])
    orders_df = pd.DataFrame()
    config = {"symbol": "SPY"}

    rule = RISK_RULE_REGISTRY["no_duplicate_entry"]
    result = rule(signal_df, positions_df, orders_df, config)

    assert bool(result.loc[0, "ok"]) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_modular_engine.py -v`
Expected: FAIL because the registries or rule implementations do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create registry modules and register the `sma_trend`, `max_position`, and `no_duplicate_entry` implementations.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_modular_engine.py -v`
Expected: PASS for the new tests.

### Task 3: Add failing tests for market-data and execution handler registries

**Files:**
- Modify: `tests/test_modular_engine.py`
- Test: `tests/test_modular_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from market_data import MARKET_DATA_PROVIDERS
from execution import EXECUTION_HANDLER_REGISTRY


def test_alpaca_market_data_provider_is_registered():
    assert "alpaca" in MARKET_DATA_PROVIDERS


def test_alpaca_paper_execution_handler_is_registered():
    assert "alpaca_paper" in EXECUTION_HANDLER_REGISTRY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_modular_engine.py -v`
Expected: FAIL because the provider and execution registries do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add the registries and register the Alpaca market-data and Alpaca paper execution handlers.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_modular_engine.py -v`
Expected: PASS for the new tests.

### Task 4: Integrate orchestrator with compatibility wrappers

**Files:**
- Modify: `engine.py`
- Modify: `alpaca_engine.py`
- Modify: `trade.ipynb`
- Test: `tests/test_modular_engine.py`
- Test: `tests/test_alpaca_engine.py`
- Test: `tests/test_trade_notebook.py`

- [ ] **Step 1: Write the failing test**

```python
from alpaca_engine import run_spy_sma_paper_bot_df


def test_compatibility_wrapper_still_returns_existing_columns():
    df = run_spy_sma_paper_bot_df(
        symbol="SPY",
        qty=1,
        submit_orders=False,
        price_df=pd.DataFrame(
            [{"symbol": "SPY", "timestamp": "2026-04-24T00:00:00+00:00", "close": 500.0, "sma20": 495.0}]
        ),
        account_df=pd.DataFrame([{"ok": True, "paper": True}]),
        has_position=False,
    )

    assert "action" in df.columns
    assert "order_submitted" in df.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_alpaca_engine.py tests/test_trade_notebook.py tests/test_modular_engine.py -v`
Expected: FAIL if wrapper compatibility breaks during refactor.

- [ ] **Step 3: Write minimal implementation**

Wire the new orchestrator into `alpaca_engine.py`, preserving existing public functions and updating the notebook to use the new config-driven bundle while keeping DataFrame outputs.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests -v`
Expected: PASS for all tests.
