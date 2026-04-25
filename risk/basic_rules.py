from __future__ import annotations

import pandas as pd

from . import register_risk_rule


def _matches_symbol(left: str, right: str) -> bool:
    return left.replace("/", "").upper() == right.replace("/", "").upper()


@register_risk_rule("max_position")
def max_position_rule(signal_df: pd.DataFrame, positions_df: pd.DataFrame, orders_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    symbol = config.get("symbol", "")
    max_position_qty = int(config.get("risk_params", {}).get("max_position_qty", 1))
    current_qty = 0
    if not positions_df.empty and "symbol" in positions_df.columns:
        matches = positions_df[positions_df["symbol"].apply(lambda value: _matches_symbol(symbol, str(value)))]
        if not matches.empty:
            current_qty = int(float(matches.iloc[0].get("qty", 0)))
    requested_qty = int(float(config.get("qty", 0)))
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
