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
