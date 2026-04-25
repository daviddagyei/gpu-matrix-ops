from pathlib import Path

import pandas as pd
from alpaca.data.enums import CryptoFeed, DataFeed
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.enums import TimeInForce

import alpaca_engine
from alpaca_engine import (
    _build_error_df,
    append_trade_log_row,
    enforce_max_position_size,
    evaluate_sma_signal_row,
    get_account_df,
    get_connection_status_df,
    get_env_config,
    get_price_data_df,
    normalize_order_response_df,
    submit_market_order_df,
    run_spy_sma_paper_bot_df,
)


def test_build_error_df_returns_standard_columns():
    df = _build_error_df(
        function_name="demo_function",
        error_type="ValueError",
        error_message="bad input",
        paper=True,
    )

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == [
        "ok",
        "paper",
        "function_name",
        "timestamp_utc",
        "error_type",
        "error_message",
    ]
    assert bool(df.loc[0, "ok"]) is False
    assert df.loc[0, "function_name"] == "demo_function"
    assert df.loc[0, "error_type"] == "ValueError"


def test_evaluate_sma_signal_row_returns_buy_when_close_above_sma_without_position():
    df = evaluate_sma_signal_row(
        symbol="SPY",
        qty=1,
        latest_close=510.0,
        latest_sma20=500.0,
        has_position=False,
    )

    assert df.loc[0, "signal"] == "BUY"
    assert bool(df.loc[0, "should_submit_order"]) is True


def test_evaluate_sma_signal_row_returns_buy_without_submit_when_position_exists():
    df = evaluate_sma_signal_row(
        symbol="SPY",
        qty=1,
        latest_close=510.0,
        latest_sma20=500.0,
        has_position=True,
    )

    assert df.loc[0, "signal"] == "BUY"
    assert bool(df.loc[0, "should_submit_order"]) is False


def test_enforce_max_position_size_blocks_when_requested_qty_exceeds_cap():
    df = enforce_max_position_size(
        symbol="SPY",
        current_qty=1,
        requested_qty=1,
        max_position_qty=1,
    )

    assert bool(df.loc[0, "ok"]) is False
    assert df.loc[0, "error_type"] == "RiskCheckFailed"


def test_append_trade_log_row_creates_csv(tmp_path: Path):
    log_path = tmp_path / "trade_log.csv"
    row = {"event_type": "signal", "symbol": "SPY", "ok": True}

    result = append_trade_log_row(row, log_path=log_path)

    assert isinstance(result, pd.DataFrame)
    assert log_path.exists()
    logged = pd.read_csv(log_path)
    assert logged.loc[0, "event_type"] == "signal"


def test_get_env_config_returns_error_df_when_keys_missing(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "")

    df = get_env_config()

    assert bool(df.loc[0, "ok"]) is False
    assert df.loc[0, "error_type"] == "MissingCredentials"


def test_get_price_data_df_returns_error_df_when_client_is_missing():
    df = get_price_data_df("SPY", data_client=None)

    assert bool(df.loc[0, "ok"]) is False
    assert df.loc[0, "error_type"] == "MissingClient"


def test_get_price_data_df_requests_iex_feed_for_notebook_friendly_access():
    captured = {}

    class FakeBarSet:
        def __init__(self):
            self.df = pd.DataFrame(
                [
                    {
                        "symbol": "SPY",
                        "timestamp": "2026-04-24T00:00:00+00:00",
                        "open": 500.0,
                        "high": 505.0,
                        "low": 499.0,
                        "close": 504.0,
                        "volume": 1000,
                    }
                ]
            )

    class FakeClient:
        def get_stock_bars(self, request):
            captured["feed"] = request.feed
            return FakeBarSet()

    df = get_price_data_df("SPY", data_client=FakeClient())

    assert captured["feed"] == DataFeed.IEX
    assert df.loc[0, "symbol"] == "SPY"


def test_get_price_data_df_supports_hourly_timeframe():
    captured = {}

    class FakeBarSet:
        def __init__(self):
            self.df = pd.DataFrame(
                [
                    {
                        "symbol": "SPY",
                        "timestamp": "2026-04-24T10:00:00+00:00",
                        "open": 500.0,
                        "high": 505.0,
                        "low": 499.0,
                        "close": 504.0,
                        "volume": 1000,
                    }
                ]
            )

    class FakeClient:
        def get_stock_bars(self, request):
            captured["timeframe"] = request.timeframe
            return FakeBarSet()

    df = get_price_data_df("SPY", timeframe="1Hour", data_client=FakeClient())

    assert str(captured["timeframe"]) == str(TimeFrame.Hour)
    assert df.loc[0, "symbol"] == "SPY"


def test_get_price_data_df_routes_btcusd_to_crypto_client():
    captured = {}

    class FakeBarSet:
        def __init__(self):
            self.df = pd.DataFrame(
                [
                    {
                        "symbol": "BTC/USD",
                        "timestamp": "2026-04-24T00:00:00+00:00",
                        "open": 90000.0,
                        "high": 91000.0,
                        "low": 89000.0,
                        "close": 90500.0,
                        "volume": 12.5,
                    }
                ]
            )

    class FakeCryptoClient:
        def get_crypto_bars(self, request, feed):
            captured["feed"] = feed
            captured["symbols"] = request.symbol_or_symbols
            return FakeBarSet()

    df = get_price_data_df("BTCUSD", crypto_data_client=FakeCryptoClient())

    assert captured["feed"] == CryptoFeed.US
    assert captured["symbols"] == ["BTC/USD"]
    assert df.loc[0, "symbol"] == "BTC/USD"


def test_get_price_data_df_accepts_standard_crypto_pair_symbol():
    captured = {}

    class FakeBarSet:
        def __init__(self):
            self.df = pd.DataFrame(
                [
                    {
                        "symbol": "BTC/USD",
                        "timestamp": "2026-04-24T00:00:00+00:00",
                        "open": 90000.0,
                        "high": 91000.0,
                        "low": 89000.0,
                        "close": 90500.0,
                        "volume": 12.5,
                    }
                ]
            )

    class FakeCryptoClient:
        def get_crypto_bars(self, request, feed):
            captured["symbols"] = request.symbol_or_symbols
            return FakeBarSet()

    df = get_price_data_df("BTC/USD", crypto_data_client=FakeCryptoClient())

    assert captured["symbols"] == ["BTC/USD"]
    assert df.loc[0, "symbol"] == "BTC/USD"


def test_get_account_df_returns_error_df_when_trading_client_is_missing():
    df = get_account_df(trading_client=None)

    assert bool(df.loc[0, "ok"]) is False
    assert df.loc[0, "error_type"] == "MissingClient"


def test_get_connection_status_df_returns_error_df_when_trading_client_is_missing():
    df = get_connection_status_df(trading_client=None)

    assert bool(df.loc[0, "ok"]) is False
    assert df.loc[0, "error_type"] == "MissingClient"


def test_normalize_order_response_df_returns_one_row():
    class Order:
        id = "abc123"
        symbol = "SPY"
        qty = "1"
        side = "buy"
        status = "accepted"
        submitted_at = "2026-04-24T00:00:00+00:00"

    df = normalize_order_response_df(Order(), paper=True)

    assert df.loc[0, "order_id"] == "abc123"
    assert bool(df.loc[0, "paper"]) is True


def test_submit_market_order_df_uses_gtc_for_crypto_symbols(monkeypatch):
    captured = {}

    class FakeOrder:
        id = "crypto-order-1"
        symbol = "BTC/USD"
        qty = "0.01"
        side = "buy"
        type = "market"
        time_in_force = "gtc"
        status = "accepted"
        submitted_at = "2026-04-24T00:00:00+00:00"

    class FakeTradingClient:
        def submit_order(self, order_data):
            captured["symbol"] = order_data.symbol
            captured["time_in_force"] = order_data.time_in_force
            return FakeOrder()

    monkeypatch.setattr(alpaca_engine, "append_trade_log_row", lambda row, log_path="logs/trade_log.csv": pd.DataFrame([row]))

    df = submit_market_order_df(
        symbol="BTCUSD",
        qty=0.01,
        side="buy",
        trading_client=FakeTradingClient(),
    )

    assert captured["symbol"] == "BTC/USD"
    assert captured["time_in_force"] == TimeInForce.GTC
    assert df.loc[0, "order_id"] == "crypto-order-1"


def test_run_spy_sma_paper_bot_df_returns_dry_run_action_when_signal_is_buy():
    bars = pd.DataFrame(
        [
            {"symbol": "SPY", "timestamp": "2026-04-23T00:00:00+00:00", "close": 500.0, "sma20": 495.0}
        ]
    )
    account = pd.DataFrame([{"ok": True, "paper": True, "buying_power": "10000"}])

    df = run_spy_sma_paper_bot_df(
        symbol="SPY",
        qty=1,
        max_position_qty=1,
        submit_orders=False,
        price_df=bars,
        account_df=account,
        has_position=False,
    )

    assert df.loc[0, "action"] == "DRY_RUN_BUY"
    assert bool(df.loc[0, "order_submitted"]) is False
