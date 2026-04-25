from __future__ import annotations

import pandas as pd

from . import register_risk_rule


def _matches_symbol(left: str, right: str) -> bool:
    return left.replace("/", "").upper() == right.replace("/", "").upper()


@register_risk_rule("max_position")
def max_position_rule(signal_df: pd.DataFrame, positions_df: pd.DataFrame, orders_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    symbol = config.get("symbol", "")
    signal = "DO_NOTHING"
    if not signal_df.empty and "signal" in signal_df.columns:
        signal = str(signal_df.iloc[0].get("signal", "DO_NOTHING"))

    if signal != "BUY":
        return pd.DataFrame(
            [
                {
                    "rule_name": "max_position",
                    "ok": True,
                    "reason": "NOT_APPLICABLE",
                    "symbol": symbol,
                }
            ]
        )

    max_position_qty = float(config.get("risk_params", {}).get("max_position_qty", 1))
    current_qty = 0.0
    if not positions_df.empty and "symbol" in positions_df.columns:
        matches = positions_df[positions_df["symbol"].apply(lambda value: _matches_symbol(symbol, str(value)))]
        if not matches.empty:
            current_qty = float(matches.iloc[0].get("qty", 0))
    requested_qty = float(config.get("qty", 0))
    ok = current_qty + requested_qty <= max_position_qty
    return pd.DataFrame(
        [
            {
                "rule_name": "max_position",
                "ok": ok,
                "reason": "" if ok else f"{symbol} position cap exceeded",
                "symbol": symbol,
            }
        ]
    )


@register_risk_rule("no_duplicate_entry")
def no_duplicate_entry_rule(signal_df: pd.DataFrame, positions_df: pd.DataFrame, orders_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    symbol = config.get("symbol", "")
    has_position = False
    has_open_order = False

    if not positions_df.empty and "symbol" in positions_df.columns:
        has_position = bool(
            not positions_df[positions_df["symbol"].apply(lambda value: _matches_symbol(symbol, str(value)))].empty
        )
    if not orders_df.empty and "symbol" in orders_df.columns:
        has_open_order = bool(
            not orders_df[orders_df["symbol"].apply(lambda value: _matches_symbol(symbol, str(value)))].empty
        )

    ok = not has_position and not has_open_order
    return pd.DataFrame(
        [
            {
                "rule_name": "no_duplicate_entry",
                "ok": ok,
                "reason": "" if ok else f"{symbol} already has a position or open order",
                "symbol": symbol,
            }
        ]
    )


@register_risk_rule("pyramiding_limit")
def pyramiding_limit_rule(signal_df: pd.DataFrame, positions_df: pd.DataFrame, orders_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    symbol = config.get("symbol", "")
    signal = "DO_NOTHING"
    if not signal_df.empty and "signal" in signal_df.columns:
        signal = str(signal_df.iloc[0].get("signal", "DO_NOTHING"))

    if signal != "BUY":
        return pd.DataFrame(
            [
                {
                    "rule_name": "pyramiding_limit",
                    "ok": True,
                    "reason": "NOT_APPLICABLE",
                    "symbol": symbol,
                }
            ]
        )

    runtime_state = config.get("runtime_state", {}).get(symbol, {})
    risk_params = config.get("risk_params", {})
    current_pyramid_count = int(runtime_state.get("pyramid_count", 0))
    max_pyramids = int(risk_params.get("max_pyramids", 0))

    if current_pyramid_count >= max_pyramids:
        return pd.DataFrame(
            [
                {
                    "rule_name": "pyramiding_limit",
                    "ok": False,
                    "reason": "MAX_PYRAMIDS_REACHED",
                    "symbol": symbol,
                }
            ]
        )

    return pd.DataFrame(
        [
            {
                "rule_name": "pyramiding_limit",
                "ok": True,
                "reason": "OK",
                "symbol": symbol,
            }
        ]
    )
