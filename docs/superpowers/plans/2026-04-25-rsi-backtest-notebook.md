# RSI Backtest Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate `BTCUSD` `5Min` `7-day` backtest notebook and reusable module for the RSI mean-reversion scalp strategy using `backtesting.py`.

**Architecture:** Keep the backtest logic in a reusable Python module and expose the workflow through a separate notebook. Reuse the project’s market-data infrastructure, add a modular RSI strategy file, and adapt data and outputs into DataFrame form for notebook use.

**Tech Stack:** Python, pandas, alpaca-py, python-dotenv, pytest, backtesting.py

---

## File Responsibilities

- `strategies/rsi_mean_reversion_scalp.py`
  RSI helpers and modular RSI scalp strategy logic.

- `backtesting_tools.py`
  `backtesting.py` adapter, data transformation, bundle outputs, and metrics extraction.

- `backtest_rsi_scalp.ipynb`
  Separate notebook for config, execution, and DataFrame output display.

- `tests/test_backtesting_tools.py`
  Unit tests for RSI helpers, adapter behavior, and bundle structure.

### Task 1: Add dependency and failing tests for backtest helpers

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_backtesting_tools.py`
- Test: `tests/test_backtesting_tools.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from backtesting_tools import to_backtesting_ohlcv_df


def test_to_backtesting_ohlcv_df_renames_columns_for_backtesting_py():
    price_df = pd.DataFrame(
        [
            {
                "timestamp": "2026-04-25T00:00:00+00:00",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
            }
        ]
    )

    result = to_backtesting_ohlcv_df(price_df)

    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_backtesting_tools.py -v`
Expected: FAIL with `ModuleNotFoundError` for `backtesting_tools`.

- [ ] **Step 3: Write minimal implementation**

Create `backtesting_tools.py` with a `to_backtesting_ohlcv_df` helper that converts normalized price data into `backtesting.py` format.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_backtesting_tools.py -v`
Expected: PASS.

### Task 2: Add failing tests for RSI strategy signals

**Files:**
- Create: `strategies/rsi_mean_reversion_scalp.py`
- Modify: `tests/test_backtesting_tools.py`
- Test: `tests/test_backtesting_tools.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from strategies.rsi_mean_reversion_scalp import build_rsi_signal_frame


def test_build_rsi_signal_frame_emits_long_entry_signal():
    price_df = pd.DataFrame(
        [
            {"timestamp": "2026-04-25T00:00:00+00:00", "close": 100},
            {"timestamp": "2026-04-25T00:05:00+00:00", "close": 98},
            {"timestamp": "2026-04-25T00:10:00+00:00", "close": 99},
            {"timestamp": "2026-04-25T00:15:00+00:00", "close": 101},
            {"timestamp": "2026-04-25T00:20:00+00:00", "close": 103},
            {"timestamp": "2026-04-25T00:25:00+00:00", "close": 104},
        ]
    )

    result = build_rsi_signal_frame(
        price_df,
        {
            "symbol": "BTCUSD",
            "strategy_params": {
                "rsi_window": 2,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
            },
        },
    )

    assert "signal" in result.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_backtesting_tools.py -v`
Expected: FAIL because the RSI strategy module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create the RSI helper and signal-frame builder, ensuring it returns a DataFrame with long/short signal annotations.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_backtesting_tools.py -v`
Expected: PASS.

### Task 3: Add failing tests for backtest bundle outputs

**Files:**
- Modify: `backtesting_tools.py`
- Modify: `tests/test_backtesting_tools.py`
- Test: `tests/test_backtesting_tools.py`

- [ ] **Step 1: Write the failing test**

```python
from backtesting_tools import build_backtest_bundle


def test_build_backtest_bundle_returns_metrics_trades_and_equity():
    bundle = build_backtest_bundle(
        price_df=price_df,
        config={
            "symbol": "BTCUSD",
            "strategy_params": {},
            "cash": 10000,
            "commission": 0.0,
        },
    )

    assert set(bundle) >= {"metrics_df", "trades_df", "equity_curve_df", "signals_df"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_backtesting_tools.py -v`
Expected: FAIL because the bundle builder does not exist or is incomplete.

- [ ] **Step 3: Write minimal implementation**

Implement the `backtesting.py` adapter and return the backtest bundle as DataFrames.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_backtesting_tools.py -v`
Expected: PASS.

### Task 4: Create the notebook and run full verification

**Files:**
- Create: `backtest_rsi_scalp.ipynb`
- Modify: `tests/test_trade_notebook.py`
- Test: `tests/test_backtesting_tools.py`
- Test: `tests/test_trade_notebook.py`

- [ ] **Step 1: Write the failing notebook test**

Add a structural test that `backtest_rsi_scalp.ipynb` contains a config cell for `BTCUSD`, `5Min`, `7` days and uses the new backtest bundle helper.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_trade_notebook.py -v`
Expected: FAIL because the backtest notebook does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create the notebook with:
- config cell
- market-data fetch
- backtest run
- metrics/trades/equity/signals output cells

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests -v`
Expected: PASS for the full suite.
