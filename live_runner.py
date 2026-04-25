import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from engine import build_symbol_config, run_engine_bundle
from registry import resolve_engine_config
from runtime_state import (
    build_initial_state,
    should_suppress_duplicate_action,
    update_symbol_state,
)


def _latest_market_bar_timestamp(bundle: dict) -> str:
    market_data_df = bundle.get("market_data_df", pd.DataFrame())
    if market_data_df.empty or "timestamp" not in market_data_df.columns:
        return ""
    return str(market_data_df.sort_values("timestamp").iloc[-1].get("timestamp", ""))


def _read_row_value(df: pd.DataFrame, column: str, default):
    if df.empty or column not in df.columns:
        return default
    return df.iloc[0].get(column, default)


def _suppress_duplicate_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame([{"execution_status": "DUPLICATE_SUPPRESSED", "order_submitted": False}])

    suppressed = summary_df.copy()
    suppressed.loc[0, "execution_status"] = "DUPLICATE_SUPPRESSED"
    suppressed.loc[0, "order_submitted"] = False
    return suppressed


def _build_preflight_config(symbol_config: dict) -> dict:
    preflight_config = dict(symbol_config)
    preflight_config["submit_orders"] = False
    return preflight_config


def append_live_runner_log(log_path, summary_df: pd.DataFrame, config: dict, symbol_state: dict) -> None:
    row = summary_df.iloc[0].to_dict() if not summary_df.empty else {}
    row["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    row["timeframe"] = config.get("timeframe", row.get("timeframe", ""))
    row["strategy"] = config.get("strategy", row.get("strategy", ""))
    row["last_processed_bar_timestamp"] = symbol_state.get("last_processed_bar_timestamp", "")
    row["pyramid_count"] = symbol_state.get("pyramid_count", 0)

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    pd.DataFrame([row]).to_csv(path, mode="a", header=write_header, index=False)


def normalize_live_symbols(config: dict) -> list[str]:
    if config.get("symbols"):
        return list(config["symbols"])
    if config.get("symbol"):
        return [config["symbol"]]
    return []


def run_live_cycle(config: dict, runtime_state: dict) -> pd.DataFrame:
    rows = []
    for symbol in normalize_live_symbols(config):
        symbol_config = build_symbol_config(config, symbol)
        symbol_config["runtime_state"] = runtime_state
        preflight_bundle = run_engine_bundle(_build_preflight_config(symbol_config))
        summary_df = preflight_bundle.get("summary_df", pd.DataFrame())
        signal_df = preflight_bundle.get("signal_df", pd.DataFrame())
        current_bar_timestamp = _latest_market_bar_timestamp(preflight_bundle)

        current_signal = _read_row_value(summary_df, "signal", _read_row_value(signal_df, "signal", ""))
        current_action = _read_row_value(summary_df, "action", _read_row_value(signal_df, "action", ""))
        order_submitted = False
        if should_suppress_duplicate_action(
            symbol_state=runtime_state.get(symbol, {}),
            current_bar_timestamp=current_bar_timestamp,
            current_signal=str(current_signal),
            current_action=str(current_action),
        ):
            summary_df = _suppress_duplicate_summary(summary_df)
        else:
            bundle = preflight_bundle
            if bool(symbol_config.get("submit_orders", False)):
                bundle = run_engine_bundle(symbol_config)
                summary_df = bundle.get("summary_df", pd.DataFrame())
                signal_df = bundle.get("signal_df", pd.DataFrame())
            current_signal = _read_row_value(summary_df, "signal", _read_row_value(signal_df, "signal", ""))
            current_action = _read_row_value(summary_df, "action", _read_row_value(signal_df, "action", ""))
            order_submitted = bool(_read_row_value(summary_df, "order_submitted", False))

        runtime_state[symbol] = update_symbol_state(
            symbol_state=runtime_state.get(symbol, {}),
            current_bar_timestamp=current_bar_timestamp,
            current_signal=str(current_signal),
            current_action=str(current_action),
            order_submitted=order_submitted,
            pyramid_increment=1 if order_submitted and str(current_signal) == "BUY" else 0,
        )

        if config.get("live_log_path"):
            append_live_runner_log(
                log_path=config["live_log_path"],
                summary_df=summary_df,
                config=config,
                symbol_state=runtime_state[symbol],
            )

        if summary_df.empty:
            rows.append({"symbol": symbol, "execution_status": "NO_SUMMARY"})
        else:
            rows.append(summary_df.iloc[0].to_dict())
    return pd.DataFrame(rows)


def run_live_loop(config: dict):
    resolved = resolve_engine_config(config)
    symbols = normalize_live_symbols(resolved)
    runtime_state = build_initial_state(symbols)
    while True:
        run_live_cycle(resolved, runtime_state)
        time.sleep(int(resolved.get("poll_interval_seconds", 30)))
