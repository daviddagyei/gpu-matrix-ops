# Modular Registry Trading Engine Design

**Date:** 2026-04-25

**Goal**

Refactor the current Alpaca paper-trading engine into a modular, registry-driven architecture where market data, strategies, risk rules, execution handlers, and engine presets can be swapped without changing the notebook interface.

## Core Direction

The notebook should remain a stable control surface. Internally, the system should be decomposed into focused modules with registries that map string names to implementations. The notebook should drive behavior through a config object and receive the same family of DataFrame outputs regardless of which strategy or preset is selected.

## Required Components

- `market_data.py`
  Owns symbol normalization, timeframe handling, lookback configuration, stock/crypto routing, and market-data provider registry.

- `strategies/`
  Contains strategy implementations. Each strategy takes normalized market data plus config and returns a standardized signal DataFrame.

- `risk/`
  Contains individual risk rules. Each rule returns a standardized rule-result DataFrame and can be combined in a risk pipeline.

- `execution.py`
  Contains execution handlers such as Alpaca paper trading plus order and cancel helpers.

- `registry.py`
  Holds component registries and engine presets. Supports direct component selection and named presets.

- `engine.py`
  Orchestrates config resolution, market-data retrieval, strategy execution, risk evaluation, position/order inspection, execution or dry-run behavior, and returns a notebook-friendly bundle of DataFrames.

- `alpaca_engine.py`
  Compatibility facade that preserves the current public notebook API while delegating to the new modular modules.

## Notebook Contract

The notebook should be able to set one config object, select a preset or explicit components, and receive a stable output bundle. Expected bundle keys:

- `settings_df`
- `market_data_df`
- `signal_df`
- `risk_df`
- `execution_df`
- `positions_df`
- `orders_df`
- `summary_df`

Each bundle entry should be a `pd.DataFrame`.

## Registry Design

Component registries:

- `MARKET_DATA_PROVIDERS`
- `STRATEGY_REGISTRY`
- `RISK_RULE_REGISTRY`
- `EXECUTION_HANDLER_REGISTRY`

Optional engine presets:

- `ENGINE_PRESETS`

Presets should define defaults for:

- market data provider
- strategy
- strategy params
- risk rules
- risk params
- execution handler
- symbol/timeframe/lookback defaults

Notebook config should be able to override preset values.

## Interface Contracts

### Market data provider

Input:
- `config`

Output:
- normalized price DataFrame with columns:
  `symbol`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `trade_count`, `vwap`

### Strategy

Input:
- `price_df`
- `config`

Output:
- one-row signal DataFrame with columns including:
  `symbol`, `strategy_name`, `signal`, `action`, `close`

### Risk rule

Input:
- `signal_df`
- `positions_df`
- `orders_df`
- `config`

Output:
- one or more rows with columns including:
  `rule_name`, `ok`, `reason`, `symbol`

### Execution handler

Input:
- `signal_df`
- `config`

Output:
- one-row execution DataFrame with columns including:
  `ok`, `order_submitted`, `order_id`, `status`, `symbol`

## Initial Strategies and Rules

Initial strategy:
- `sma_trend`
  Buy when latest close is above the configured SMA window and the position is not already open.

Initial risk rules:
- `max_position`
- `no_duplicate_entry`

Initial execution handler:
- `alpaca_paper`

Initial market-data provider:
- `alpaca`

Initial preset:
- `alpaca_sma_default`

## Timeframe Extensibility

Timeframe should be owned by `market_data.py` rather than strategy code. Strategies should consume normalized bars without knowing whether the bars are daily, hourly, or minute-based. This keeps strategy modules focused on signal logic rather than transport or provider details.

## Backward Compatibility

Existing notebook-facing functions in `alpaca_engine.py` should continue working:

- `get_connection_status_df`
- `get_account_df`
- `get_price_data_df`
- `get_positions_df`
- `get_open_orders_df`
- `generate_spy_sma_signal_df`
- `submit_market_order_df`
- `cancel_open_orders_df`
- `run_spy_sma_paper_bot_df`

They may delegate into the new modules but should preserve DataFrame returns.

## Testing Goals

Add unit coverage for:

- registry lookup and preset resolution
- config override behavior
- strategy registry execution
- risk pipeline execution
- bundle structure returned by the new orchestrator
- backward compatibility of the old public API

Live Alpaca verification remains useful as smoke testing, but default tests should remain deterministic and not require network access.
