from __future__ import annotations

from typing import Any

import pandas as pd
from backtesting import Strategy
from backtesting.lib import FractionalBacktest

from alpaca_engine import get_price_data_df
from strategies.rsi_mean_reversion_scalp import _calculate_rsi, build_rsi_signal_frame


def _empty_backtest_bundle(config: dict, price_df: pd.DataFrame, error_type: str, error_message: str) -> dict[str, pd.DataFrame]:
    metrics_df = pd.DataFrame(
        [
            {
                "ok": False,
                "error_type": error_type,
                "error_message": error_message,
            }
        ]
    )
    return {
        "settings_df": pd.DataFrame([config]),
        "metrics_df": metrics_df,
        "trades_df": pd.DataFrame(),
        "equity_curve_df": pd.DataFrame(),
        "signals_df": pd.DataFrame(),
        "price_df": price_df,
    }


def to_backtesting_ohlcv_df(price_df: pd.DataFrame) -> pd.DataFrame:
    working_df = price_df.copy()
    if "timestamp" in working_df.columns:
        working_df["timestamp"] = pd.to_datetime(working_df["timestamp"], utc=True, errors="coerce")
        working_df = working_df.sort_values("timestamp").set_index("timestamp")
        working_df.index = working_df.index.tz_localize(None)

    renamed = working_df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column not in renamed.columns:
            renamed[column] = pd.NA
    ohlcv_df = renamed[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
    ohlcv_df["Volume"] = ohlcv_df["Volume"].fillna(0)
    ohlcv_df = ohlcv_df.dropna(subset=["Open", "High", "Low", "Close"])
    return ohlcv_df


def _build_strategy_class(config: dict):
    params = config.get("strategy_params", {})
    rsi_window = int(params.get("rsi_window", 5))
    oversold_threshold = float(params.get("oversold_threshold", 30))
    overbought_threshold = float(params.get("overbought_threshold", 70))
    exit_threshold = float(params.get("exit_threshold", 50))
    short_exit_threshold = float(params.get("short_exit_threshold", 50))
    stop_loss_pct = float(params.get("stop_loss_pct", 0.004))
    take_profit_pct = float(params.get("take_profit_pct", 0.006))
    qty = float(config.get("qty", 0.001))
    fractional_unit = float(config.get("fractional_unit", qty if qty > 0 else 0.001))
    order_size = max(1, int(round(qty / fractional_unit)))

    class RsiMeanReversionScalpBacktestStrategy(Strategy):
        def init(self):
            self.rsi = self.I(lambda close: _calculate_rsi(pd.Series(close), rsi_window).to_numpy(), self.data.Close)

        def next(self):
            if len(self.rsi) < 2:
                return

            previous_rsi = self.rsi[-2]
            latest_rsi = self.rsi[-1]
            latest_close = float(self.data.Close[-1])

            if pd.isna(previous_rsi) or pd.isna(latest_rsi):
                return

            if not self.position:
                if previous_rsi < oversold_threshold and latest_rsi >= oversold_threshold:
                    self.buy(
                        size=order_size,
                        sl=latest_close * (1 - stop_loss_pct),
                        tp=latest_close * (1 + take_profit_pct),
                    )
                elif previous_rsi > overbought_threshold and latest_rsi <= overbought_threshold:
                    self.sell(
                        size=order_size,
                        sl=latest_close * (1 + stop_loss_pct),
                        tp=latest_close * (1 - take_profit_pct),
                    )
                return

            if self.position.is_long and latest_rsi >= exit_threshold:
                self.position.close()
            elif self.position.is_short and latest_rsi <= short_exit_threshold:
                self.position.close()

    return RsiMeanReversionScalpBacktestStrategy, fractional_unit


def _extract_metrics_df(stats: pd.Series) -> pd.DataFrame:
    fields = [
        "Start",
        "End",
        "Duration",
        "Exposure Time [%]",
        "Equity Final [$]",
        "Equity Peak [$]",
        "Return [%]",
        "Buy & Hold Return [%]",
        "Max. Drawdown [%]",
        "# Trades",
        "Win Rate [%]",
        "Best Trade [%]",
        "Worst Trade [%]",
        "Avg. Trade [%]",
        "Profit Factor",
    ]
    row = {field: stats.get(field, pd.NA) for field in fields}
    return pd.DataFrame([row])


def build_backtest_bundle(price_df: pd.DataFrame | None = None, config: dict | None = None) -> dict[str, pd.DataFrame]:
    config = {} if config is None else dict(config)
    if price_df is None:
        price_df = get_price_data_df(
            symbol=config.get("symbol", "BTCUSD"),
            timeframe=config.get("timeframe", "5Min"),
            lookback_days=int(config.get("lookback_days", 7)),
        )
    if price_df.empty:
        return _empty_backtest_bundle(config, price_df, "NoPriceData", "No price data returned for backtest")
    if "ok" in price_df.columns and not bool(price_df.iloc[0].get("ok", True)):
        return _empty_backtest_bundle(
            config,
            price_df,
            str(price_df.iloc[0].get("error_type", "PriceDataError")),
            str(price_df.iloc[0].get("error_message", "Price data fetch failed")),
        )

    signals_df = build_rsi_signal_frame(price_df, config)
    bt_price_df = to_backtesting_ohlcv_df(price_df)
    if bt_price_df.empty:
        return _empty_backtest_bundle(
            config,
            price_df,
            "NoUsableOHLCV",
            "No usable OHLCV rows remained after cleaning backtest price data",
        )

    strategy_cls, fractional_unit = _build_strategy_class(config)
    backtest = FractionalBacktest(
        bt_price_df,
        strategy_cls,
        cash=float(config.get("cash", 10000)),
        commission=float(config.get("commission", 0.0)),
        trade_on_close=bool(config.get("trade_on_close", True)),
        exclusive_orders=bool(config.get("exclusive_orders", True)),
        finalize_trades=True,
        fractional_unit=fractional_unit,
    )
    stats = backtest.run()

    trades_df = stats.get("_trades", pd.DataFrame()).copy()
    equity_curve_df = stats.get("_equity_curve", pd.DataFrame()).copy()
    if isinstance(equity_curve_df, pd.DataFrame):
        equity_curve_df = equity_curve_df.reset_index().rename(columns={"index": "timestamp"})
    return {
        "settings_df": pd.DataFrame([config]),
        "metrics_df": _extract_metrics_df(stats),
        "trades_df": trades_df,
        "equity_curve_df": equity_curve_df,
        "signals_df": signals_df,
        "price_df": price_df,
    }
