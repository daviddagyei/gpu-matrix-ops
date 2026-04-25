# RSI Backtest Notebook Design

**Date:** 2026-04-25

**Goal**

Add a separate notebook and reusable module to backtest an RSI mean-reversion scalp strategy on `BTCUSD` using `5Min` bars over the last `7 days`, returning notebook-friendly DataFrames for metrics, trades, signals, and equity.

## Direction

Use `backtesting.py` as the underlying trusted backtest library, but keep the project-specific logic in local modules so the notebook stays simple and future strategies can reuse the same data and reporting patterns.

## Components

- `strategies/rsi_mean_reversion_scalp.py`
  Modular RSI strategy logic with a DataFrame-returning strategy function for research and a parameter contract compatible with the project registry model.

- `backtesting_tools.py`
  Reusable helpers that:
  - fetch market data through the current market-data path
  - transform project bars into `backtesting.py` OHLCV format
  - define the `backtesting.py` strategy adapter
  - run the backtest
  - return metrics, trades, signals, and equity curve as DataFrames

- `backtest_rsi_scalp.ipynb`
  Separate notebook for configuring the backtest and viewing its outputs.

## Strategy Behavior

The strategy should support both long and short trades.

Long side:
- enter when RSI crosses back above the oversold threshold
- exit on RSI recovery to the exit threshold, stop loss, or take profit

Short side:
- enter when RSI crosses back below the overbought threshold
- exit on RSI reversion to the short exit threshold, stop loss, or take profit

This produces more signals than a long-only version and better matches the earlier requirement to support long and short.

## Notebook Contract

Notebook config should include:

- `symbol`
- `timeframe`
- `lookback_days`
- `cash`
- `commission`
- `trade_on_close`
- `exclusive_orders`
- `strategy_params`

Notebook outputs should include:

- `settings_df`
- `metrics_df`
- `trades_df`
- `equity_curve_df`
- `signals_df`
- `price_df`

All should be pandas DataFrames.

## Metrics

Metrics should include at least:

- total return
- buy and hold return
- equity final
- equity peak
- max drawdown
- number of trades
- win rate
- best trade
- worst trade
- average trade
- profit factor

## Testing Goals

Add deterministic tests for:

- RSI calculation helper
- signal generation for both long and short entries
- adapter conversion from market-data DataFrame to `backtesting.py` input DataFrame
- backtest result bundle structure

Network access should not be required for unit tests.
