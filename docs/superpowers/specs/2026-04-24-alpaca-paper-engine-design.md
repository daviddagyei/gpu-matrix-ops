# Alpaca Paper Engine Design

**Date:** 2026-04-24

**Goal**

Build a notebook-friendly Alpaca paper-trading engine that `trade.ipynb` can import directly. Public functions should return `pandas.DataFrame` objects, keep terminal output minimal, and support paper-account order submission from the notebook.

## Scope

This design covers:

- Alpaca paper-account connection checks.
- Account, position, open-order, and bar-data retrieval.
- A simple SPY 20-day SMA strategy.
- Paper market-order submission and open-order cancellation.
- CSV audit logging for bot runs and order attempts.
- Thin script wrappers for connection testing and bot execution.
- Small unit tests for DataFrame contracts and strategy behavior.

This design does not cover:

- Live trading.
- Short selling or multi-asset portfolio logic.
- Streaming market data.
- Advanced order types.
- A production scheduler or deployment setup.

## Architecture

The implementation uses one importable module, `alpaca_engine.py`, as the notebook engine. It owns configuration loading, Alpaca client creation, DataFrame normalization, strategy logic, logging, risk checks, and paper order submission. This keeps the initial version simple for notebook use while leaving room to split responsibilities into smaller modules later.

Two small scripts, `test_connection.py` and `paper_bot.py`, act as wrappers around the engine. They should print returned DataFrames without extra chatter so they can serve as simple smoke tests.

## Public API

All public notebook-facing functions return `pd.DataFrame`.

### Status and account functions

- `get_connection_status_df()`
  Returns one row describing whether the paper account is reachable and which account metadata is available.

- `get_account_df()`
  Returns one row with account status and financial summary fields.

### Market and portfolio functions

- `get_price_data_df(symbol: str, lookback_days: int = 60, timeframe: str = "1Day")`
  Returns normalized OHLCV bar data plus `sma20`.

- `get_positions_df()`
  Returns zero or more rows representing current open positions.

- `get_open_orders_df(symbol: str | None = None)`
  Returns zero or more rows representing open orders, optionally filtered by symbol.

### Strategy and execution functions

- `generate_spy_sma_signal_df(symbol: str = "SPY", qty: int = 1)`
  Returns one row with latest close, latest SMA value, holding state, signal, and recommended action.

- `submit_market_order_df(symbol: str, qty: int, side: str, time_in_force: str = "day")`
  Submits a paper market order and returns one status row describing the order response.

- `cancel_open_orders_df(symbol: str | None = None)`
  Cancels open paper orders and returns zero or more rows summarizing cancel results.

- `run_spy_sma_paper_bot_df(symbol: str = "SPY", qty: int = 1, max_position_qty: int = 1, submit_orders: bool = False)`
  Runs the high-level workflow: account check, bar fetch, signal generation, safety checks, optional order submission, and one final result row.

## DataFrame Contract

Public functions must always return DataFrames, including failures and no-op outcomes. The notebook should not need to parse exceptions to understand normal outcomes.

### Standard error/status columns

Every status-style DataFrame should include:

- `ok`
- `paper`
- `function_name`
- `timestamp_utc`
- `error_type`
- `error_message`

Success rows should use `ok=True` and empty error fields. Error rows should use `ok=False` with structured error metadata.

### Function-specific fields

- `get_connection_status_df()` should include:
  `account_id`, `account_number`, `status`, `currency`, `buying_power`, `portfolio_value`

- `get_account_df()` should include:
  `account_id`, `status`, `cash`, `buying_power`, `equity`, `portfolio_value`, `long_market_value`, `short_market_value`

- `get_price_data_df()` should include:
  `symbol`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `trade_count`, `vwap`, `sma20`

- `get_positions_df()` should include:
  `symbol`, `qty`, `side`, `market_value`, `avg_entry_price`, `current_price`, `unrealized_pl`

- `get_open_orders_df()` should include:
  `order_id`, `symbol`, `qty`, `side`, `type`, `time_in_force`, `status`, `submitted_at`

- `generate_spy_sma_signal_df()` should include:
  `symbol`, `qty`, `close`, `sma20`, `has_position`, `signal`, `should_submit_order`

- `submit_market_order_df()` should include:
  `symbol`, `qty`, `side`, `order_id`, `status`, `submitted_at`

- `run_spy_sma_paper_bot_df()` should include:
  `symbol`, `qty`, `close`, `sma20`, `signal`, `action`, `order_submitted`, `order_id`, `has_position`, `max_position_qty`

## Safety Rules

The engine must enforce these rules before placing paper orders:

- `paper=True` is mandatory for trading client creation and execution.
- API keys must exist in environment variables loaded from `.env`.
- Duplicate long entry should be blocked if the symbol is already held.
- Requested quantity plus current position quantity must not exceed `max_position_qty`.
- Strategy execution should support `submit_orders=False` so notebook runs can stay dry-run by default.
- Cancellation helpers should be available so open orders can be cleared explicitly.

## Logging

The engine should create `logs/trade_log.csv` on first write and append one compact row for:

- Bot runs.
- Order submission attempts.
- Order cancellation attempts.
- Engine-level errors returned as DataFrame rows.

Logging should stay file-based and should not add verbose terminal output.

## Error Handling

Notebook-facing paths should prefer structured error DataFrames over raised exceptions. Internal helpers may still raise when useful, but public functions should catch failures and convert them into a one-row error DataFrame with the standard columns.

## Dependencies

Initial dependencies:

- `alpaca-py`
- `pandas`
- `python-dotenv`
- `pytest`

## Testing Approach

Unit tests should focus on:

- Standard DataFrame status/error shape.
- Signal-generation behavior for buy/no-op cases.
- Position-limit guard behavior.
- Log-row writing behavior.

Tests should not depend on live Alpaca network access. Live verification should happen through the wrapper scripts and the notebook itself.

## File Layout

- `alpaca_engine.py`
  Core engine and notebook-facing API.

- `test_connection.py`
  Thin script calling `get_connection_status_df()`.

- `paper_bot.py`
  Thin script calling `run_spy_sma_paper_bot_df(..., submit_orders=True)`.

- `requirements.txt`
  Minimal dependency list.

- `tests/test_alpaca_engine.py`
  Unit tests for DataFrame contracts and strategy/risk logic.

- `logs/.gitkeep`
  Keeps the logs directory present in the workspace.

## Notebook Usage

Expected notebook flow:

1. Import notebook-facing functions from `alpaca_engine.py`.
2. Run `get_connection_status_df()` and `get_account_df()`.
3. Inspect `get_price_data_df("SPY")`.
4. Inspect `generate_spy_sma_signal_df("SPY", qty=1)`.
5. Execute `run_spy_sma_paper_bot_df("SPY", qty=1, submit_orders=True)` when ready to place a paper order.

This design keeps the notebook in control while moving trading mechanics into a reusable engine.
