from __future__ import annotations

from typing import Callable

import pandas as pd


EXECUTION_HANDLER_REGISTRY: dict[str, Callable[[pd.DataFrame, dict], pd.DataFrame]] = {}


def register_execution_handler(name: str):
    def decorator(func):
        EXECUTION_HANDLER_REGISTRY[name] = func
        return func

    return decorator


@register_execution_handler("alpaca_paper")
def alpaca_paper_execution_handler(signal_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    from alpaca_engine import submit_market_order_df

    signal = signal_df.iloc[0].get("signal", "DO_NOTHING")
    action = signal_df.iloc[0].get("action", "DO_NOTHING")
    should_submit = bool(signal_df.iloc[0].get("should_submit_order", False))

    if not should_submit or signal != "BUY":
        return pd.DataFrame(
            [
                {
                    "ok": True,
                    "order_submitted": False,
                    "order_id": "",
                    "status": "NO_ACTION",
                    "symbol": config["symbol"],
                    "action": action,
                }
            ]
        )

    if not bool(config.get("submit_orders", False)):
        return pd.DataFrame(
            [
                {
                    "ok": True,
                    "order_submitted": False,
                    "order_id": "",
                    "status": "DRY_RUN",
                    "symbol": config["symbol"],
                    "action": "DRY_RUN_BUY",
                }
            ]
        )

    order_df = submit_market_order_df(
        symbol=config["symbol"],
        qty=config["qty"],
        side="buy",
    )
    row = order_df.iloc[0].to_dict()
    return pd.DataFrame(
        [
            {
                "ok": bool(row.get("ok", False)),
                "order_submitted": bool(row.get("ok", False)),
                "order_id": row.get("order_id", ""),
                "status": row.get("status", ""),
                "symbol": row.get("symbol", config["symbol"]),
                "action": "BUY_SUBMITTED" if bool(row.get("ok", False)) else "BUY_FAILED",
            }
        ]
    )
