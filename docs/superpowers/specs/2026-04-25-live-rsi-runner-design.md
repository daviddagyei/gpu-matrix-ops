# Live RSI Runner Design

## Goal

Add a modular live runner for Alpaca paper/live execution that can process one or many symbols sequentially, evaluate on the current in-progress bar, support long-only pyramiding, and fully close positions on exit signals.

## Why

The current system supports:

- one-shot engine runs
- modular strategies, risk rules, and execution handlers
- notebook-based inspection
- backtesting for the RSI mean reversion scalp strategy

It does not yet support continuous execution. The next step is a runtime layer that can keep evaluating and trading until manually stopped, while preserving the existing modular architecture.

## Scope

This design covers:

- continuous live runner loop
- multi-symbol configuration
- sequential per-symbol processing
- long-only Alpaca-compatible execution
- pyramiding support with configurable caps
- full close on exit
- duplicate-bar and duplicate-order protection
- registry preset for live RSI trading

This design does not cover:

- short selling in live mode
- parallel symbol workers
- websocket market data
- broker-specific implementations beyond Alpaca

## Constraints

- Alpaca crypto cannot be sold short.
- Alpaca equity shorting requires margin eligibility and is outside the target workflow.
- The runner should work for real scenarios the user expects to trade, so live mode should be long-only.
- Polling should be conservative for Alpaca free/basic rate limits.
- The notebook interface should remain stable and DataFrame-first.

## High-Level Architecture

The existing engine remains responsible for one symbol at a time. A new live runtime layer repeatedly builds per-symbol configs and invokes the engine in a controlled loop.

### Components

- `live_runner.py`
  Owns the continuous loop, symbol iteration, polling, stop behavior, and per-cycle logging.

- `runtime_state.py`
  Stores and updates per-symbol runtime state such as last processed bar, pyramid count, last executed action, and cooldown timestamps.

- `capabilities.py`
  Defines capability profiles like `alpaca_crypto_long_only` so execution can reject unsupported actions without strategy-specific hacks.

- `registry.py`
  Adds a live preset, likely `alpaca_rsi_scalp_live`.

- `execution.py`
  Extends execution handling to support long-only live behavior:
  - enter/add with `BUY`
  - fully close with `SELL`
  - reject short-side actions cleanly

- `risk/basic_rules.py`
  Adds pyramiding-specific rules and cooldown checks.

## Config Contract

Live config should stay compatible with the current engine config and add only runtime fields.

Example:

```python
live_config = {
    "preset": "alpaca_rsi_scalp_live",
    "symbols": ["BTCUSD", "ETHUSD"],
    "timeframe": "5Min",
    "lookback_days": 7,
    "qty": 0.001,
    "submit_orders": True,
    "poll_interval_seconds": 30,
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
}
```

### Config Rules

- `symbol` remains valid for one-shot engine usage.
- `symbols` is the live-runner field for sequential multi-symbol processing.
- Each loop iteration builds a symbol-specific resolved config from the shared live config.
- `poll_interval_seconds` defaults to `30`.

## Live Cycle

For each loop cycle:

1. Iterate through `symbols` one at a time.
2. Build a symbol-specific config.
3. Fetch current market data using the configured timeframe and lookback.
4. Load current positions and open orders.
5. Load runtime state for the symbol.
6. Run strategy.
7. Run risk rules.
8. Reject unsupported actions via the capability profile.
9. Suppress duplicate execution if the current bar and action were already handled.
10. Submit order if allowed.
11. Update runtime state.
12. Append a one-row cycle result for inspection/logging.
13. After all symbols are processed, sleep for `poll_interval_seconds`.

The runner continues until manually interrupted.

## In-Progress Bar Behavior

The runner evaluates on the latest in-progress bar, not just fully closed bars. This better matches the desired real-time trading behavior.

Because of that, duplicate protection is mandatory. The system must not repeatedly fire the same action every polling cycle just because the current bar is still open.

## Position Behavior

### Entry

- If flat and the strategy emits `BUY`, enter a long position.
- If already long and the strategy emits `BUY`, pyramiding is allowed if risk checks pass.

### Pyramiding

Pyramiding is allowed but bounded:

- enforce `max_position_qty`
- enforce `max_pyramids`
- enforce `pyramid_cooldown_seconds`

The runner should treat repeated adds as distinct actions only when they pass these bounds.

### Exit

- If the strategy emits `SELL`, close the full long position for that symbol.
- No scale-out logic in the first version.

## Capability Profiles

The first live profile should be:

```python
{
    "name": "alpaca_crypto_long_only",
    "supports_long": True,
    "supports_short": False,
    "supports_fractional": True,
    "supports_pyramiding": True,
}
```

If a strategy emits unsupported actions such as `SELL_SHORT` or `BUY_TO_COVER`, execution should return a clear no-op or blocked result DataFrame rather than failing unexpectedly.

## Runtime State

Per-symbol runtime state should include:

- `last_processed_bar_timestamp`
- `last_signal`
- `last_action`
- `last_order_timestamp`
- `pyramid_count`

This state is needed for:

- duplicate-bar suppression
- cooldown enforcement
- controlled pyramiding

The first version can keep runtime state in memory for the active process. Persistence across restarts is not required.

## Duplicate Protection

Duplicate protection should be enforced at two levels:

### Bar-Level Guard

If the latest bar timestamp matches `last_processed_bar_timestamp` and the engine is about to repeat the same action, suppress the order.

### Execution-Level Guard

If the last executed action and last order timestamp indicate a recent identical order attempt inside the cooldown window, suppress the new order.

These two guards together reduce accidental repeated orders caused by in-progress bar polling, retries, or temporary API instability.

## Risk Changes

The current risk system should be extended with a pyramiding-focused rule.

Expected rule behavior:

- allow first entry if within total size limits
- allow subsequent adds only if:
  - current qty + requested qty <= `max_position_qty`
  - current pyramid count < `max_pyramids`
  - cooldown has expired
- block otherwise with clear reasons in `risk_df`

## Notebook and CLI Interface

The notebook should remain for:

- config editing
- one-shot inspection
- viewing result DataFrames

Continuous execution should run from a script entry point such as `run_live.py` or directly via `live_runner.py`.

This keeps the notebook stable while giving the live process a cleaner operational path.

## Testing Strategy

Add targeted tests for:

- symbol-by-symbol sequential processing
- live preset resolution
- capability profile blocking of short signals
- pyramiding limit and cooldown enforcement
- duplicate-bar suppression
- full-close behavior on `SELL`
- long-only execution handler behavior

No live Alpaca execution should be required for unit tests.

## Recommended First Preset

Add:

```python
"alpaca_rsi_scalp_live"
```

with defaults:

- `strategy = "rsi_mean_reversion_scalp"`
- `timeframe = "5Min"`
- `poll_interval_seconds = 30`
- `capability_profile = "alpaca_crypto_long_only"`
- pyramiding enabled with conservative caps

## Success Criteria

The extension is successful when:

- the runner can process one or many symbols sequentially
- it evaluates every `30` seconds by default
- it can add to long positions via pyramiding within configured limits
- it fully closes long positions on exit signals
- it avoids duplicate orders on the same in-progress bar
- unsupported short actions are blocked cleanly
- the notebook-facing one-shot interface remains consistent
