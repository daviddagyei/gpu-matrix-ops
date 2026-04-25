from __future__ import annotations

import pandas as pd

from execution import EXECUTION_HANDLER_REGISTRY
from market_data import MARKET_DATA_PROVIDERS
from registry import resolve_engine_config
from risk import RISK_RULE_REGISTRY
from strategies import STRATEGY_REGISTRY


def _error_or_empty_df(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def build_symbol_config(config: dict, symbol: str) -> dict:
    symbol_config = dict(config)
    symbol_config["symbol"] = symbol
    return symbol_config


def _run_risk_rules(signal_df: pd.DataFrame, positions_df: pd.DataFrame, orders_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for rule_name in config.get("risk_rules", []):
        rule = RISK_RULE_REGISTRY[rule_name]
        result_df = rule(signal_df, positions_df, orders_df, config)
        rows.extend(result_df.to_dict("records"))
    if not rows:
        return pd.DataFrame(columns=["rule_name", "ok", "reason", "symbol"])
    return pd.DataFrame(rows)


def run_engine_bundle(config: dict | None = None) -> dict[str, pd.DataFrame]:
    from alpaca_engine import get_open_orders_df, get_positions_df

    resolved = resolve_engine_config(config)
    settings_df = pd.DataFrame([resolved])

    market_data_provider = MARKET_DATA_PROVIDERS[resolved["market_data_provider"]]
    market_data_df = market_data_provider(resolved)

    positions_df = get_positions_df()
    orders_df = get_open_orders_df(symbol=resolved["symbol"])

    strategy = STRATEGY_REGISTRY[resolved["strategy"]]
    signal_df = strategy(market_data_df if "ok" not in market_data_df.columns else pd.DataFrame(), resolved)

    should_run_risk_rules = True
    if not signal_df.empty:
        signal_value = str(signal_df.iloc[0].get("signal", "DO_NOTHING"))
        should_submit_order = bool(signal_df.iloc[0].get("should_submit_order", signal_value != "DO_NOTHING"))
        should_run_risk_rules = should_submit_order and signal_value != "DO_NOTHING"

    risk_df = _error_or_empty_df(["rule_name", "ok", "reason", "symbol"])
    if should_run_risk_rules:
        risk_df = _run_risk_rules(
            signal_df,
            positions_df if "ok" not in positions_df.columns else pd.DataFrame(),
            orders_df if "ok" not in orders_df.columns else pd.DataFrame(),
            resolved,
        )

    if should_run_risk_rules and not risk_df.empty and not risk_df["ok"].all():
        failing = risk_df[~risk_df["ok"]].iloc[0]
        signal_df = signal_df.copy()
        signal_df.loc[0, "should_submit_order"] = False
        signal_df.loc[0, "action"] = "BLOCKED_BY_RISK"
        execution_df = pd.DataFrame(
            [
                {
                    "ok": False,
                    "order_submitted": False,
                    "order_id": "",
                    "status": "BLOCKED_BY_RISK",
                    "symbol": resolved["symbol"],
                    "action": failing["reason"],
                }
            ]
        )
    else:
        execution_handler = EXECUTION_HANDLER_REGISTRY[resolved["execution_handler"]]
        execution_df = execution_handler(signal_df, resolved)

    summary_row = {
        "symbol": resolved["symbol"],
        "timeframe": resolved.get("timeframe", ""),
        "strategy": resolved["strategy"],
        "risk_rules": ",".join(resolved.get("risk_rules", [])),
        "submit_orders": bool(resolved.get("submit_orders", False)),
    }
    if not signal_df.empty:
        summary_row["signal"] = signal_df.iloc[0].get("signal", "")
        summary_row["action"] = signal_df.iloc[0].get("action", "")
    if not execution_df.empty:
        summary_row["execution_status"] = execution_df.iloc[0].get("status", "")
        summary_row["order_submitted"] = execution_df.iloc[0].get("order_submitted", False)
    summary_df = pd.DataFrame([summary_row])

    return {
        "settings_df": settings_df,
        "market_data_df": market_data_df,
        "signal_df": signal_df,
        "risk_df": risk_df,
        "execution_df": execution_df,
        "positions_df": positions_df,
        "orders_df": orders_df,
        "summary_df": summary_df,
    }
