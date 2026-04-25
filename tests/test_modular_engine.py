import pandas as pd

from alpaca_engine import run_spy_sma_paper_bot_df
from engine import run_engine_bundle
from execution import EXECUTION_HANDLER_REGISTRY
from market_data import MARKET_DATA_PROVIDERS
from registry import resolve_engine_config
from risk import RISK_RULE_REGISTRY
from strategies import STRATEGY_REGISTRY


def test_resolve_engine_config_applies_preset_and_overrides():
    config = resolve_engine_config(
        {
            "preset": "alpaca_sma_default",
            "symbol": "BTCUSD",
            "timeframe": "1Hour",
        }
    )

    assert config["symbol"] == "BTCUSD"
    assert config["timeframe"] == "1Hour"
    assert config["strategy"] == "sma_trend"


def test_live_rsi_preset_resolves_expected_defaults():
    config = resolve_engine_config({"preset": "alpaca_rsi_scalp_live"})

    assert config["market_data_provider"] == "alpaca"
    assert config["strategy"] == "rsi_mean_reversion_scalp"
    assert config["strategy_params"] == {
        "rsi_window": 5,
        "oversold_threshold": 30,
        "overbought_threshold": 70,
        "exit_threshold": 50,
        "short_exit_threshold": 50,
        "stop_loss_pct": 0.004,
        "take_profit_pct": 0.006,
    }
    assert config["risk_rules"] == ["pyramiding_limit"]
    assert config["risk_params"] == {
        "max_pyramids": 10,
        "pyramid_cooldown_seconds": 60,
    }
    assert config["execution_handler"] == "alpaca_paper"
    assert config["capability_profile"] == "alpaca_crypto_long_only"
    assert config["symbols"] == ["BTCUSD"]
    assert config["timeframe"] == "5Min"
    assert config["lookback_days"] == 7
    assert config["qty"] == 0.001
    assert config["submit_orders"] is False
    assert config["poll_interval_seconds"] == 30


def test_run_engine_bundle_does_not_block_do_nothing_signal_with_risk(monkeypatch):
    def fake_alpaca_market_data_provider(config: dict) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": config["symbol"], "timestamp": "2026-04-24T00:00:00+00:00", "close": 100.0}])

    def fake_get_positions_df():
        return pd.DataFrame([{"symbol": "BTCUSD", "qty": 99}])

    def fake_get_open_orders_df(symbol: str | None = None):
        return pd.DataFrame()

    import alpaca_engine

    monkeypatch.setitem(MARKET_DATA_PROVIDERS, "alpaca", fake_alpaca_market_data_provider)
    monkeypatch.setattr(alpaca_engine, "get_positions_df", fake_get_positions_df)
    monkeypatch.setattr(alpaca_engine, "get_open_orders_df", fake_get_open_orders_df)

    bundle = run_engine_bundle(
        {
            "preset": "alpaca_rsi_scalp_live",
            "symbol": "BTCUSD",
            "submit_orders": True,
            "strategy_params": {
                "rsi_window": 5,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "exit_threshold": 50,
                "short_exit_threshold": 50,
                "stop_loss_pct": 0.004,
                "take_profit_pct": 0.006,
            },
        }
    )

    assert bundle["signal_df"].iloc[0]["signal"] == "DO_NOTHING"
    assert bundle["execution_df"].iloc[0]["status"] == "NO_ACTION"
    assert bundle["summary_df"].iloc[0]["execution_status"] == "NO_ACTION"
    assert bundle["risk_df"].empty


def test_run_engine_bundle_returns_expected_bundle_keys(monkeypatch):
    def fake_alpaca_market_data_provider(config: dict) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "symbol": config["symbol"],
                    "timestamp": "2026-04-24T00:00:00+00:00",
                    "close": 500.0,
                    "sma20": 495.0,
                }
            ]
        )

    def fake_get_positions_df():
        return pd.DataFrame(columns=["symbol", "qty", "side", "market_value", "avg_entry_price", "current_price", "unrealized_pl"])

    def fake_get_open_orders_df(symbol: str | None = None):
        return pd.DataFrame(columns=["order_id", "symbol", "qty", "side", "type", "time_in_force", "status", "submitted_at"])

    import alpaca_engine

    monkeypatch.setitem(MARKET_DATA_PROVIDERS, "alpaca", fake_alpaca_market_data_provider)
    monkeypatch.setattr(alpaca_engine, "get_positions_df", fake_get_positions_df)
    monkeypatch.setattr(alpaca_engine, "get_open_orders_df", fake_get_open_orders_df)

    bundle = run_engine_bundle(
        {
            "preset": "alpaca_sma_default",
            "symbol": "SPY",
            "submit_orders": False,
        }
    )

    assert set(bundle) >= {
        "settings_df",
        "market_data_df",
        "signal_df",
        "risk_df",
        "execution_df",
        "positions_df",
        "orders_df",
        "summary_df",
    }
    assert bundle["market_data_df"].shape == (1, 4)
    assert bundle["signal_df"].iloc[0]["signal"] == "BUY"
    assert bundle["summary_df"].iloc[0]["execution_status"] == "DRY_RUN"


def test_sma_trend_strategy_is_registered():
    assert "sma_trend" in STRATEGY_REGISTRY


def test_no_duplicate_entry_rule_blocks_existing_position():
    signal_df = pd.DataFrame([{"symbol": "SPY", "signal": "BUY", "action": "BUY"}])
    positions_df = pd.DataFrame([{"symbol": "SPY", "qty": "1"}])
    orders_df = pd.DataFrame()
    config = {"symbol": "SPY"}

    rule = RISK_RULE_REGISTRY["no_duplicate_entry"]
    result = rule(signal_df, positions_df, orders_df, config)

    assert bool(result.loc[0, "ok"]) is False


def test_alpaca_market_data_provider_is_registered():
    assert "alpaca" in MARKET_DATA_PROVIDERS


def test_alpaca_paper_execution_handler_is_registered():
    assert "alpaca_paper" in EXECUTION_HANDLER_REGISTRY


def test_compatibility_wrapper_still_returns_existing_columns():
    df = run_spy_sma_paper_bot_df(
        symbol="SPY",
        qty=1,
        submit_orders=False,
        price_df=pd.DataFrame(
            [{"symbol": "SPY", "timestamp": "2026-04-24T00:00:00+00:00", "close": 500.0, "sma20": 495.0}]
        ),
        account_df=pd.DataFrame([{"ok": True, "paper": True}]),
        has_position=False,
    )

    assert "action" in df.columns
    assert "order_submitted" in df.columns
