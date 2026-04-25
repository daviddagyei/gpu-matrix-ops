from __future__ import annotations

import pandas as pd

from . import register_strategy


@register_strategy("sma_trend")
def sma_trend_strategy(price_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    symbol = config.get("symbol", "")
    strategy_name = "sma_trend"
    sma_window = int(config.get("strategy_params", {}).get("sma_window", 20))

    if price_df.empty or "close" not in price_df.columns:
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "strategy_name": strategy_name,
                    "signal": "DO_NOTHING",
                    "action": "NO_PRICE_DATA",
                    "close": pd.NA,
                    "indicator_values": f"sma_window={sma_window}",
                    "should_submit_order": False,
                }
            ]
        )

    working_df = price_df.copy()
    if "sma20" not in working_df.columns or sma_window != 20:
        working_df["sma_value"] = pd.to_numeric(working_df["close"], errors="coerce").rolling(sma_window).mean()
    else:
        working_df["sma_value"] = working_df["sma20"]

    latest = working_df.sort_values("timestamp").iloc[-1]
    latest_close = float(latest["close"])
    latest_sma = latest["sma_value"]

    if pd.isna(latest_sma):
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "strategy_name": strategy_name,
                    "signal": "DO_NOTHING",
                    "action": "NOT_ENOUGH_DATA",
                    "close": latest_close,
                    "indicator_values": f"sma_window={sma_window};sma_value=nan",
                    "should_submit_order": False,
                }
            ]
        )

    signal = "BUY" if latest_close > float(latest_sma) else "DO_NOTHING"
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "strategy_name": strategy_name,
                "signal": signal,
                "action": signal,
                "close": latest_close,
                "indicator_values": f"sma_window={sma_window};sma_value={float(latest_sma)}",
                "should_submit_order": signal == "BUY",
            }
        ]
    )
