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


def test_run_engine_bundle_returns_expected_bundle_keys():
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
