from __future__ import annotations

from copy import deepcopy


ENGINE_PRESETS = {
    "alpaca_sma_default": {
        "market_data_provider": "alpaca",
        "strategy": "sma_trend",
        "strategy_params": {
            "sma_window": 20,
        },
        "risk_rules": ["max_position", "no_duplicate_entry"],
        "risk_params": {
            "max_position_qty": 1,
        },
        "execution_handler": "alpaca_paper",
        "symbol": "SPY",
        "timeframe": "1Day",
        "lookback_days": 60,
        "qty": 1,
        "submit_orders": False,
    },
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
        "risk_rules": ["pyramiding_limit"],
        "risk_params": {
            "max_pyramids": 10,
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
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def resolve_engine_config(config: dict | None = None) -> dict:
    config = {} if config is None else deepcopy(config)
    preset_name = config.get("preset")
    base = {}
    if preset_name:
        base = deepcopy(ENGINE_PRESETS[preset_name])
        base["preset"] = preset_name
    return _deep_merge(base, config)
