from __future__ import annotations

from typing import Callable

import pandas as pd

from capabilities import CAPABILITY_PROFILES


EXECUTION_HANDLER_REGISTRY: dict[str, Callable[[pd.DataFrame, dict], pd.DataFrame]] = {}


def register_execution_handler(name: str):
    def decorator(func):
        EXECUTION_HANDLER_REGISTRY[name] = func
        return func

    return decorator


def _to_order_qty(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _resolve_sell_position_qty(config: dict) -> tuple[float, str]:
    from alpaca_engine import _symbols_match, get_positions_df

    explicit_position_qty = _to_order_qty(config.get("position_qty"))
    if explicit_position_qty > 0:
        return explicit_position_qty, ""

    positions_df = config.get("positions_df")
    if positions_df is None:
        positions_df = get_positions_df()

    if not isinstance(positions_df, pd.DataFrame):
        return 0.0, "POSITION_QTY_UNAVAILABLE"
    if "ok" in positions_df.columns and not positions_df.empty and not bool(positions_df.loc[0, "ok"]):
        return 0.0, "POSITION_QTY_UNAVAILABLE"
    if positions_df.empty or "symbol" not in positions_df.columns or "qty" not in positions_df.columns:
        return 0.0, "NO_POSITION_TO_CLOSE"

    matches = positions_df[positions_df["symbol"].apply(lambda value: _symbols_match(config["symbol"], str(value)))]
    if matches.empty:
        return 0.0, "NO_POSITION_TO_CLOSE"

    sell_qty = _to_order_qty(matches.iloc[0]["qty"])
    if sell_qty <= 0:
        return 0.0, "NO_POSITION_TO_CLOSE"
    return sell_qty, ""


@register_execution_handler("alpaca_paper")
def alpaca_paper_execution_handler(signal_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    from alpaca_engine import submit_market_order_df

    signal = signal_df.iloc[0].get("signal", "DO_NOTHING")
    action = signal_df.iloc[0].get("action", "DO_NOTHING")
    should_submit = bool(signal_df.iloc[0].get("should_submit_order", False))
    profile = CAPABILITY_PROFILES.get(config.get("capability_profile", ""), {})

    if signal in {"SELL_SHORT", "BUY_TO_COVER"} and not bool(profile.get("supports_short", False)):
        return pd.DataFrame(
            [
                {
                    "ok": False,
                    "order_submitted": False,
                    "order_id": "",
                    "status": "UNSUPPORTED_ACTION",
                    "symbol": config["symbol"],
                    "action": signal,
                }
            ]
        )

    if not should_submit or signal not in {"BUY", "SELL"}:
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
        dry_run_action = "DRY_RUN_BUY" if signal == "BUY" else "DRY_RUN_SELL"
        return pd.DataFrame(
            [
                {
                    "ok": True,
                    "order_submitted": False,
                    "order_id": "",
                    "status": "DRY_RUN",
                    "symbol": config["symbol"],
                    "action": dry_run_action,
                }
            ]
        )

    order_qty = config["qty"]
    if signal == "SELL":
        order_qty, sell_error = _resolve_sell_position_qty(config)
        if sell_error:
            return pd.DataFrame(
                [
                    {
                        "ok": False,
                        "order_submitted": False,
                        "order_id": "",
                        "status": sell_error,
                        "symbol": config["symbol"],
                        "action": signal,
                    }
                ]
            )

    order_df = submit_market_order_df(
        symbol=config["symbol"],
        qty=order_qty,
        side="sell" if signal == "SELL" else "buy",
    )
    row = order_df.iloc[0].to_dict()
    submitted_action = f"{signal}_SUBMITTED"
    failed_action = f"{signal}_FAILED"
    return pd.DataFrame(
        [
            {
                "ok": bool(row.get("ok", False)),
                "order_submitted": bool(row.get("ok", False)),
                "order_id": row.get("order_id", ""),
                "status": row.get("status", ""),
                "symbol": row.get("symbol", config["symbol"]),
                "action": submitted_action if bool(row.get("ok", False)) else failed_action,
            }
        ]
    )
