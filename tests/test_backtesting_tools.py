import pandas as pd

from backtesting_tools import build_backtest_bundle, to_backtesting_ohlcv_df
from strategies.rsi_mean_reversion_scalp import build_rsi_signal_frame


def test_to_backtesting_ohlcv_df_renames_columns_for_backtesting_py():
    price_df = pd.DataFrame(
        [
            {
                "timestamp": "2026-04-25T00:00:00+00:00",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
            }
        ]
    )

    result = to_backtesting_ohlcv_df(price_df)

    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_to_backtesting_ohlcv_df_drops_rows_with_missing_ohlc():
    price_df = pd.DataFrame(
        [
            {
                "timestamp": "2026-04-25T00:00:00+00:00",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10.0,
            },
            {
                "timestamp": "2026-04-25T00:05:00+00:00",
                "open": 101.0,
                "high": None,
                "low": 100.0,
                "close": 101.5,
                "volume": 11.0,
            },
        ]
    )

    result = to_backtesting_ohlcv_df(price_df)

    assert len(result) == 1
    assert result["Close"].iloc[0] == 100.5


def test_build_rsi_signal_frame_returns_signal_column():
    price_df = pd.DataFrame(
        [
            {"timestamp": "2026-04-25T00:00:00+00:00", "close": 100},
            {"timestamp": "2026-04-25T00:05:00+00:00", "close": 98},
            {"timestamp": "2026-04-25T00:10:00+00:00", "close": 99},
            {"timestamp": "2026-04-25T00:15:00+00:00", "close": 101},
            {"timestamp": "2026-04-25T00:20:00+00:00", "close": 103},
            {"timestamp": "2026-04-25T00:25:00+00:00", "close": 104},
        ]
    )

    result = build_rsi_signal_frame(
        price_df,
        {
            "symbol": "BTCUSD",
            "strategy_params": {
                "rsi_window": 2,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "exit_threshold": 50,
                "short_exit_threshold": 50,
            },
        },
    )

    assert "signal" in result.columns


def test_build_backtest_bundle_returns_metrics_trades_and_equity():
    price_df = pd.DataFrame(
        [
            {"timestamp": "2026-04-25T00:00:00+00:00", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
            {"timestamp": "2026-04-25T00:05:00+00:00", "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 11.0},
            {"timestamp": "2026-04-25T00:10:00+00:00", "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0, "volume": 12.0},
            {"timestamp": "2026-04-25T00:15:00+00:00", "open": 102.0, "high": 104.0, "low": 101.0, "close": 103.0, "volume": 13.0},
            {"timestamp": "2026-04-25T00:20:00+00:00", "open": 103.0, "high": 104.0, "low": 100.0, "close": 101.0, "volume": 14.0},
            {"timestamp": "2026-04-25T00:25:00+00:00", "open": 101.0, "high": 102.0, "low": 97.0, "close": 98.0, "volume": 15.0},
            {"timestamp": "2026-04-25T00:30:00+00:00", "open": 98.0, "high": 99.0, "low": 95.0, "close": 96.0, "volume": 16.0},
        ]
    )

    bundle = build_backtest_bundle(
        price_df=price_df,
        config={
            "symbol": "BTCUSD",
            "strategy_params": {
                "rsi_window": 2,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "exit_threshold": 50,
                "short_exit_threshold": 50,
            },
            "cash": 10000,
            "commission": 0.0,
            "trade_on_close": True,
        },
    )

    assert set(bundle) >= {"metrics_df", "trades_df", "equity_curve_df", "signals_df"}


def test_build_backtest_bundle_handles_error_price_frame():
    price_df = pd.DataFrame(
        [
            {
                "ok": False,
                "paper": True,
                "function_name": "get_price_data_df",
                "timestamp_utc": "2026-04-25T00:00:00+00:00",
                "error_type": "ConnectionError",
                "error_message": "DNS failed",
            }
        ]
    )

    bundle = build_backtest_bundle(
        price_df=price_df,
        config={
            "symbol": "BTCUSD",
            "timeframe": "5Min",
            "lookback_days": 7,
        },
    )

    assert bundle["metrics_df"].iloc[0]["ok"] == False
    assert bundle["metrics_df"].iloc[0]["error_type"] == "ConnectionError"
    assert bundle["trades_df"].empty
