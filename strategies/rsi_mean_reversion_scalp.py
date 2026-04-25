from __future__ import annotations

import numpy as np
import pandas as pd

from . import register_strategy


def _calculate_rsi(close: pd.Series, window: int) -> pd.Series:
    close = pd.to_numeric(close, errors="coerce")
    delta = close.diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.rolling(window).mean()
    avg_loss = losses.rolling(window).mean()
    avg_loss = avg_loss.replace(0, np.nan)

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def build_rsi_signal_frame(price_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    symbol = config.get("symbol", "")
    params = config.get("strategy_params", {})
    rsi_window = int(params.get("rsi_window", 5))
    oversold_threshold = float(params.get("oversold_threshold", 30))
    overbought_threshold = float(params.get("overbought_threshold", 70))
    exit_threshold = float(params.get("exit_threshold", 50))
    short_exit_threshold = float(params.get("short_exit_threshold", 50))

    if price_df.empty or "close" not in price_df.columns:
        return pd.DataFrame(
            columns=[
                "symbol",
                "timestamp",
                "close",
                "rsi",
                "signal",
                "action",
                "long_entry",
                "short_entry",
                "long_exit",
                "short_exit",
            ]
        )

    working_df = price_df.copy()
    if "timestamp" in working_df.columns:
        working_df = working_df.sort_values("timestamp")
    working_df["close"] = pd.to_numeric(working_df["close"], errors="coerce")
    working_df["rsi"] = _calculate_rsi(working_df["close"], rsi_window)
    working_df["previous_rsi"] = working_df["rsi"].shift(1)

    working_df["long_entry"] = (
        (working_df["previous_rsi"] < oversold_threshold)
        & (working_df["rsi"] >= oversold_threshold)
    )
    working_df["short_entry"] = (
        (working_df["previous_rsi"] > overbought_threshold)
        & (working_df["rsi"] <= overbought_threshold)
    )
    working_df["long_exit"] = working_df["rsi"] >= exit_threshold
    working_df["short_exit"] = working_df["rsi"] <= short_exit_threshold

    signal = pd.Series("DO_NOTHING", index=working_df.index, dtype="object")
    action = pd.Series("NO_SIGNAL", index=working_df.index, dtype="object")

    signal = signal.mask(working_df["long_entry"], "BUY")
    action = action.mask(working_df["long_entry"], "RSI_CROSSED_BACK_ABOVE_OVERSOLD")
    signal = signal.mask(working_df["short_entry"], "SELL_SHORT")
    action = action.mask(working_df["short_entry"], "RSI_CROSSED_BACK_BELOW_OVERBOUGHT")
    signal = signal.mask(~working_df["long_entry"] & ~working_df["short_entry"] & working_df["long_exit"], "SELL")
    action = action.mask(~working_df["long_entry"] & ~working_df["short_entry"] & working_df["long_exit"], "RSI_RECOVERED_TO_EXIT_THRESHOLD")
    signal = signal.mask(~working_df["long_entry"] & ~working_df["short_entry"] & ~working_df["long_exit"] & working_df["short_exit"], "BUY_TO_COVER")
    action = action.mask(~working_df["long_entry"] & ~working_df["short_entry"] & ~working_df["long_exit"] & working_df["short_exit"], "RSI_REVERTED_TO_SHORT_EXIT_THRESHOLD")

    working_df["symbol"] = symbol
    working_df["signal"] = signal
    working_df["action"] = action

    columns = [
        "symbol",
        "timestamp",
        "close",
        "rsi",
        "signal",
        "action",
        "long_entry",
        "short_entry",
        "long_exit",
        "short_exit",
    ]
    return working_df[columns].reset_index(drop=True)


@register_strategy("rsi_mean_reversion_scalp")
def rsi_mean_reversion_scalp_strategy(price_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    symbol = config.get("symbol", "")
    strategy_name = "rsi_mean_reversion_scalp"
    params = config.get("strategy_params", {})
    in_position = bool(config.get("in_position", False))
    position_side = config.get("position_side", "")
    entry_price = config.get("entry_price", None)
    stop_loss_pct = float(params.get("stop_loss_pct", 0.004))
    take_profit_pct = float(params.get("take_profit_pct", 0.006))

    signal_frame = build_rsi_signal_frame(price_df, config)
    if signal_frame.empty:
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "strategy_name": strategy_name,
                    "signal": "DO_NOTHING",
                    "action": "NO_PRICE_DATA",
                    "close": pd.NA,
                    "indicator_values": "",
                    "should_submit_order": False,
                }
            ]
        )

    latest = signal_frame.iloc[-1]
    latest_close = latest["close"]
    latest_rsi = latest["rsi"]
    signal = "DO_NOTHING"
    action = "NO_SIGNAL"

    if not in_position:
        if bool(latest["long_entry"]):
            signal = "BUY"
            action = latest["action"]
        elif bool(latest["short_entry"]):
            signal = "SELL_SHORT"
            action = latest["action"]
    else:
        if position_side == "long":
            if bool(latest["long_exit"]):
                signal = "SELL"
                action = "RSI_RECOVERED_TO_EXIT_THRESHOLD"
            if entry_price is not None:
                entry_price = float(entry_price)
                if float(latest_close) <= entry_price * (1 - stop_loss_pct):
                    signal = "SELL"
                    action = "STOP_LOSS_HIT"
                elif float(latest_close) >= entry_price * (1 + take_profit_pct):
                    signal = "SELL"
                    action = "TAKE_PROFIT_HIT"
        elif position_side == "short":
            if bool(latest["short_exit"]):
                signal = "BUY_TO_COVER"
                action = "RSI_REVERTED_TO_SHORT_EXIT_THRESHOLD"
            if entry_price is not None:
                entry_price = float(entry_price)
                if float(latest_close) >= entry_price * (1 + stop_loss_pct):
                    signal = "BUY_TO_COVER"
                    action = "STOP_LOSS_HIT"
                elif float(latest_close) <= entry_price * (1 - take_profit_pct):
                    signal = "BUY_TO_COVER"
                    action = "TAKE_PROFIT_HIT"

    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "strategy_name": strategy_name,
                "signal": signal,
                "action": action,
                "close": latest_close,
                "indicator_values": f"rsi_value={latest_rsi}",
                "should_submit_order": signal != "DO_NOTHING",
            }
        ]
    )
