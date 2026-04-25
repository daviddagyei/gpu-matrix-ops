# Alpaca Paper Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a notebook-friendly Alpaca paper-trading engine with DataFrame-only public returns, CSV audit logging, SPY SMA signal generation, and thin wrapper scripts for connection and bot execution.

**Architecture:** Keep v1 centered on one importable module, `alpaca_engine.py`, so `trade.ipynb` can call a stable API directly. Use small internal helpers for environment loading, client creation, DataFrame normalization, strategy checks, risk checks, and logging, while exposing public DataFrame-returning functions for account, market data, and paper execution flows.

**Tech Stack:** Python, pandas, alpaca-py, python-dotenv, pytest

---

## File Responsibilities

- `requirements.txt`
  Dependency list for runtime and tests.

- `alpaca_engine.py`
  Core engine module. Owns configuration helpers, client helpers, DataFrame/error utilities, market/account retrieval, strategy logic, risk checks, CSV logging, and public API functions.

- `test_connection.py`
  Thin script that prints the DataFrame from `get_connection_status_df()`.

- `paper_bot.py`
  Thin script that prints the DataFrame from `run_spy_sma_paper_bot_df(symbol="SPY", qty=1, submit_orders=True)`.

- `tests/test_alpaca_engine.py`
  Unit tests for status/error DataFrame shape, signal logic, risk guards, and logging.

- `logs/.gitkeep`
  Keeps `logs/` present.

### Task 1: Create dependencies and red tests for the engine contract

**Files:**
- Create: `requirements.txt`
- Create: `tests/test_alpaca_engine.py`
- Test: `tests/test_alpaca_engine.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from alpaca_engine import _build_error_df, evaluate_sma_signal_row


def test_build_error_df_returns_standard_columns():
    df = _build_error_df(
        function_name="demo_function",
        error_type="ValueError",
        error_message="bad input",
        paper=True,
    )

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == [
        "ok",
        "paper",
        "function_name",
        "timestamp_utc",
        "error_type",
        "error_message",
    ]
    assert df.loc[0, "ok"] is False
    assert df.loc[0, "function_name"] == "demo_function"
    assert df.loc[0, "error_type"] == "ValueError"


def test_evaluate_sma_signal_row_returns_buy_when_close_above_sma_without_position():
    df = evaluate_sma_signal_row(
        symbol="SPY",
        qty=1,
        latest_close=510.0,
        latest_sma20=500.0,
        has_position=False,
    )

    assert df.loc[0, "signal"] == "BUY"
    assert df.loc[0, "should_submit_order"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: FAIL with `ModuleNotFoundError` for `alpaca_engine` or missing function imports.

- [ ] **Step 3: Write minimal implementation**

```python
from datetime import datetime, timezone

import pandas as pd


def _build_error_df(function_name: str, error_type: str, error_message: str, paper: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ok": False,
                "paper": paper,
                "function_name": function_name,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": error_type,
                "error_message": error_message,
            }
        ]
    )


def evaluate_sma_signal_row(
    symbol: str,
    qty: int,
    latest_close: float,
    latest_sma20: float,
    has_position: bool,
) -> pd.DataFrame:
    should_buy = latest_close > latest_sma20 and not has_position
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "qty": qty,
                "close": latest_close,
                "sma20": latest_sma20,
                "has_position": has_position,
                "signal": "BUY" if latest_close > latest_sma20 else "DO_NOTHING",
                "should_submit_order": should_buy,
            }
        ]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: PASS for both tests.

### Task 2: Build engine helpers and expand unit coverage

**Files:**
- Create: `alpaca_engine.py`
- Modify: `tests/test_alpaca_engine.py`
- Test: `tests/test_alpaca_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pandas as pd

from alpaca_engine import append_trade_log_row, evaluate_sma_signal_row, enforce_max_position_size


def test_evaluate_sma_signal_row_returns_do_nothing_when_position_exists():
    df = evaluate_sma_signal_row(
        symbol="SPY",
        qty=1,
        latest_close=510.0,
        latest_sma20=500.0,
        has_position=True,
    )

    assert df.loc[0, "signal"] == "BUY"
    assert df.loc[0, "should_submit_order"] is False


def test_enforce_max_position_size_blocks_when_requested_qty_exceeds_cap():
    df = enforce_max_position_size(
        symbol="SPY",
        current_qty=1,
        requested_qty=1,
        max_position_qty=1,
    )

    assert df.loc[0, "ok"] is False
    assert df.loc[0, "error_type"] == "RiskCheckFailed"


def test_append_trade_log_row_creates_csv(tmp_path: Path):
    log_path = tmp_path / "trade_log.csv"
    row = {"event_type": "signal", "symbol": "SPY", "ok": True}

    result = append_trade_log_row(row, log_path=log_path)

    assert isinstance(result, pd.DataFrame)
    assert log_path.exists()
    logged = pd.read_csv(log_path)
    assert logged.loc[0, "event_type"] == "signal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: FAIL because `enforce_max_position_size` and `append_trade_log_row` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
from pathlib import Path


def enforce_max_position_size(symbol: str, current_qty: int, requested_qty: int, max_position_qty: int) -> pd.DataFrame:
    total_qty = current_qty + requested_qty
    if total_qty > max_position_qty:
        return _build_error_df(
            function_name="enforce_max_position_size",
            error_type="RiskCheckFailed",
            error_message=f"{symbol} position cap exceeded",
        )
    return pd.DataFrame(
        [
            {
                "ok": True,
                "paper": True,
                "function_name": "enforce_max_position_size",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": "",
                "error_message": "",
                "symbol": symbol,
                "current_qty": current_qty,
                "requested_qty": requested_qty,
                "max_position_qty": max_position_qty,
            }
        ]
    )


def append_trade_log_row(row: dict, log_path: str | Path = "logs/trade_log.csv") -> pd.DataFrame:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([row])
    if path.exists():
        frame.to_csv(path, mode="a", header=False, index=False)
    else:
        frame.to_csv(path, index=False)
    return frame
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: PASS for all current tests.

### Task 3: Add environment/client helpers and account/data public functions

**Files:**
- Modify: `alpaca_engine.py`
- Modify: `tests/test_alpaca_engine.py`
- Test: `tests/test_alpaca_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from alpaca_engine import get_env_config, get_price_data_df


def test_get_env_config_returns_error_df_when_keys_missing(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

    df = get_env_config()

    assert df.loc[0, "ok"] is False
    assert df.loc[0, "error_type"] == "MissingCredentials"


def test_get_price_data_df_returns_error_df_when_client_is_missing():
    df = get_price_data_df("SPY", data_client=None)

    assert df.loc[0, "ok"] is False
    assert df.loc[0, "error_type"] == "MissingClient"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: FAIL because `get_env_config` does not exist or `get_price_data_df` does not accept `data_client`.

- [ ] **Step 3: Write minimal implementation**

```python
import os
from datetime import timedelta

from dotenv import load_dotenv


def get_env_config() -> pd.DataFrame:
    load_dotenv()
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        return _build_error_df(
            function_name="get_env_config",
            error_type="MissingCredentials",
            error_message="ALPACA_API_KEY and ALPACA_SECRET_KEY are required",
        )
    return pd.DataFrame(
        [
            {
                "ok": True,
                "paper": True,
                "function_name": "get_env_config",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": "",
                "error_message": "",
                "api_key": api_key,
                "secret_key": secret_key,
            }
        ]
    )


def get_price_data_df(symbol: str, lookback_days: int = 60, timeframe: str = "1Day", data_client=None) -> pd.DataFrame:
    if data_client is None:
        return _build_error_df(
            function_name="get_price_data_df",
            error_type="MissingClient",
            error_message="StockHistoricalDataClient is required",
        )
    return pd.DataFrame()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: PASS for the new error-path tests and existing tests.

### Task 4: Finish public Alpaca engine functions and notebook wrappers

**Files:**
- Modify: `alpaca_engine.py`
- Create: `test_connection.py`
- Create: `paper_bot.py`
- Create: `logs/.gitkeep`
- Test: `tests/test_alpaca_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from alpaca_engine import run_spy_sma_paper_bot_df


def test_run_spy_sma_paper_bot_df_returns_dry_run_action_when_signal_is_buy():
    bars = pd.DataFrame(
        [
            {"symbol": "SPY", "timestamp": "2026-04-23T00:00:00+00:00", "close": 500.0, "sma20": 495.0}
        ]
    )
    account = pd.DataFrame([{"ok": True, "paper": True, "buying_power": "10000"}])

    df = run_spy_sma_paper_bot_df(
        symbol="SPY",
        qty=1,
        max_position_qty=1,
        submit_orders=False,
        price_df=bars,
        account_df=account,
        has_position=False,
    )

    assert df.loc[0, "action"] == "DRY_RUN_BUY"
    assert df.loc[0, "order_submitted"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: FAIL because `run_spy_sma_paper_bot_df` is missing or does not support injected DataFrames.

- [ ] **Step 3: Write minimal implementation**

```python
def run_spy_sma_paper_bot_df(
    symbol: str = "SPY",
    qty: int = 1,
    max_position_qty: int = 1,
    submit_orders: bool = False,
    price_df: pd.DataFrame | None = None,
    account_df: pd.DataFrame | None = None,
    has_position: bool | None = None,
) -> pd.DataFrame:
    if price_df is None or price_df.empty:
        return _build_error_df(
            function_name="run_spy_sma_paper_bot_df",
            error_type="MissingPriceData",
            error_message="Price data is required",
        )

    latest = price_df.sort_values("timestamp").iloc[-1]
    position_flag = bool(has_position)
    signal_df = evaluate_sma_signal_row(
        symbol=symbol,
        qty=qty,
        latest_close=float(latest["close"]),
        latest_sma20=float(latest["sma20"]),
        has_position=position_flag,
    )
    action = "DRY_RUN_BUY" if bool(signal_df.loc[0, "should_submit_order"]) and not submit_orders else "DO_NOTHING"
    return pd.DataFrame(
        [
            {
                "ok": True,
                "paper": True,
                "function_name": "run_spy_sma_paper_bot_df",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": "",
                "error_message": "",
                "symbol": symbol,
                "qty": qty,
                "close": float(latest["close"]),
                "sma20": float(latest["sma20"]),
                "signal": signal_df.loc[0, "signal"],
                "action": action,
                "order_submitted": False,
                "order_id": "",
                "has_position": position_flag,
                "max_position_qty": max_position_qty,
            }
        ]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: PASS for all tests.

### Task 5: Integrate live Alpaca clients, order/cancel flows, and final verification

**Files:**
- Modify: `alpaca_engine.py`
- Modify: `test_connection.py`
- Modify: `paper_bot.py`
- Test: `tests/test_alpaca_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from alpaca_engine import normalize_order_response_df


def test_normalize_order_response_df_returns_one_row():
    class Order:
        id = "abc123"
        symbol = "SPY"
        qty = "1"
        side = "buy"
        status = "accepted"
        submitted_at = "2026-04-24T00:00:00+00:00"

    df = normalize_order_response_df(Order(), paper=True)

    assert df.loc[0, "order_id"] == "abc123"
    assert df.loc[0, "paper"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: FAIL because `normalize_order_response_df` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def normalize_order_response_df(order, paper: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ok": True,
                "paper": paper,
                "function_name": "normalize_order_response_df",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": "",
                "error_message": "",
                "order_id": str(getattr(order, "id", "")),
                "symbol": str(getattr(order, "symbol", "")),
                "qty": str(getattr(order, "qty", "")),
                "side": str(getattr(order, "side", "")),
                "status": str(getattr(order, "status", "")),
                "submitted_at": str(getattr(order, "submitted_at", "")),
            }
        ]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: PASS for all tests.

- [ ] **Step 5: Run full verification**

Run: `pytest tests/test_alpaca_engine.py -v`
Expected: PASS

Run: `python test_connection.py`
Expected: prints a one-row DataFrame with `ok=True` when valid Alpaca paper credentials are available.

Run: `python paper_bot.py`
Expected: prints a one-row DataFrame showing the signal outcome and, when conditions are met and credentials are valid, a paper-order response or dry-run/no-op action.
