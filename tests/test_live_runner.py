import pandas as pd

from engine import build_symbol_config
from capabilities import CAPABILITY_PROFILES
from execution import alpaca_paper_execution_handler
from live_runner import normalize_live_symbols, run_live_cycle
from risk import RISK_RULE_REGISTRY
from runtime_state import build_initial_state, should_suppress_duplicate_action, update_symbol_state


def test_alpaca_crypto_long_only_profile_exists():
    profile = CAPABILITY_PROFILES["alpaca_crypto_long_only"]

    assert profile["supports_long"] is True
    assert profile["supports_short"] is False
    assert profile["supports_fractional"] is True
    assert profile["supports_pyramiding"] is True


def test_build_initial_state_creates_symbol_state():
    state = build_initial_state(["BTCUSD", "ETHUSD"])

    assert state["BTCUSD"]["pyramid_count"] == 0
    assert state["BTCUSD"]["last_processed_bar_timestamp"] == ""
    assert state["ETHUSD"]["last_action"] == ""
    assert state["BTCUSD"]["last_signal"] == ""
    assert state["BTCUSD"]["last_order_timestamp"] == ""


def test_normalize_live_symbols_uses_symbols_field_when_present():
    result = normalize_live_symbols({"symbols": ["BTCUSD", "ETHUSD"]})

    assert result == ["BTCUSD", "ETHUSD"]


def test_should_suppress_duplicate_action_returns_true_for_same_bar_and_signal():
    symbol_state = {
        "last_processed_bar_timestamp": "2026-04-25T12:00:00+00:00",
        "last_signal": "BUY",
        "last_action": "BUY",
        "last_order_timestamp": "2026-04-25T12:00:10+00:00",
        "pyramid_count": 1,
    }

    assert should_suppress_duplicate_action(
        symbol_state=symbol_state,
        current_bar_timestamp="2026-04-25T12:00:00+00:00",
        current_signal="BUY",
        current_action="BUY_SUBMITTED",
    ) is True


def test_should_suppress_duplicate_action_returns_false_without_bar_timestamp():
    symbol_state = {
        "last_processed_bar_timestamp": "2026-04-25T12:00:00+00:00",
        "last_signal": "BUY",
        "last_action": "BUY_SUBMITTED",
        "last_order_timestamp": "2026-04-25T12:00:10+00:00",
        "pyramid_count": 1,
    }

    assert should_suppress_duplicate_action(
        symbol_state=symbol_state,
        current_bar_timestamp="",
        current_signal="BUY",
        current_action="BUY_SUBMITTED",
    ) is False


def test_update_symbol_state_tracks_processed_bar_and_action():
    symbol_state = {
        "last_processed_bar_timestamp": "",
        "last_signal": "",
        "last_action": "",
        "last_order_timestamp": "",
        "pyramid_count": 0,
    }

    updated = update_symbol_state(
        symbol_state,
        current_bar_timestamp="2026-04-25T12:00:00+00:00",
        current_signal="BUY",
        current_action="BUY",
        order_submitted=True,
        pyramid_increment=1,
    )

    assert updated["last_processed_bar_timestamp"] == "2026-04-25T12:00:00+00:00"
    assert updated["last_signal"] == "BUY"
    assert updated["last_action"] == "BUY"
    assert updated["last_order_timestamp"] != ""
    assert updated["pyramid_count"] == 1
    assert symbol_state["last_processed_bar_timestamp"] == ""


def test_run_live_cycle_updates_symbol_state_after_buy_submission(monkeypatch):
    runtime_state = {
        "BTCUSD": {
            "last_processed_bar_timestamp": "",
            "last_signal": "",
            "last_action": "",
            "last_order_timestamp": "",
            "pyramid_count": 0,
        }
    }
    calls: list[bool] = []

    def fake_run_engine_bundle(config):
        calls.append(bool(config.get("submit_orders", False)))
        return {
            "market_data_df": pd.DataFrame([{"timestamp": "2026-04-25T12:00:00+00:00"}]),
            "summary_df": pd.DataFrame(
                [
                    {
                        "symbol": config["symbol"],
                        "execution_status": "accepted",
                        "signal": "BUY",
                        "action": "BUY_SUBMITTED",
                        "order_submitted": True,
                    }
                ]
            ),
            "signal_df": pd.DataFrame([{"signal": "BUY", "action": "BUY_SUBMITTED"}]),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    run_live_cycle({"symbols": ["BTCUSD"], "submit_orders": True}, runtime_state=runtime_state)

    assert calls == [False, True]
    assert runtime_state["BTCUSD"]["last_processed_bar_timestamp"] == "2026-04-25T12:00:00+00:00"
    assert runtime_state["BTCUSD"]["last_signal"] == "BUY"
    assert runtime_state["BTCUSD"]["last_action"] == "BUY_SUBMITTED"
    assert runtime_state["BTCUSD"]["last_order_timestamp"] != ""
    assert runtime_state["BTCUSD"]["pyramid_count"] == 1


def test_run_live_cycle_processes_single_symbol_config(monkeypatch):
    runtime_state = {
        "BTCUSD": {
            "last_processed_bar_timestamp": "",
            "last_signal": "",
            "last_action": "",
            "last_order_timestamp": "",
            "pyramid_count": 0,
        }
    }
    calls: list[bool] = []

    def fake_run_engine_bundle(config):
        calls.append(bool(config.get("submit_orders", False)))
        return {
            "market_data_df": pd.DataFrame([{"timestamp": "2026-04-25T12:00:00+00:00"}]),
            "summary_df": pd.DataFrame(
                [
                    {
                        "symbol": config["symbol"],
                        "execution_status": "accepted",
                        "signal": "BUY",
                        "action": "BUY_SUBMITTED",
                        "order_submitted": True,
                    }
                ]
            ),
            "signal_df": pd.DataFrame([{"signal": "BUY", "action": "BUY_SUBMITTED"}]),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    result = run_live_cycle({"symbol": "BTCUSD", "submit_orders": True}, runtime_state=runtime_state)

    assert calls == [False, True]
    assert list(result["symbol"]) == ["BTCUSD"]
    assert runtime_state["BTCUSD"]["last_processed_bar_timestamp"] == "2026-04-25T12:00:00+00:00"
    assert runtime_state["BTCUSD"]["pyramid_count"] == 1


def test_run_live_cycle_suppresses_duplicate_same_bar_with_preflight_live_label_mismatch(monkeypatch):
    runtime_state = {
        "BTCUSD": {
            "last_processed_bar_timestamp": "2026-04-25T12:00:00+00:00",
            "last_signal": "SELL",
            "last_action": "SELL_SUBMITTED",
            "last_order_timestamp": "2026-04-25T12:00:10+00:00",
            "pyramid_count": 1,
        }
    }
    calls: list[bool] = []

    def fake_run_engine_bundle(config):
        calls.append(bool(config.get("submit_orders", False)))
        if bool(config.get("submit_orders", False)):
            raise AssertionError("duplicate cycle should not invoke live submit path")
        return {
            "market_data_df": pd.DataFrame([{"timestamp": "2026-04-25T12:00:00+00:00"}]),
            "summary_df": pd.DataFrame(
                [
                    {
                        "symbol": config["symbol"],
                        "execution_status": "DRY_RUN",
                        "signal": "SELL",
                        "action": "DRY_RUN_SELL",
                        "order_submitted": False,
                    }
                ]
            ),
            "signal_df": pd.DataFrame([{"signal": "SELL", "action": "DRY_RUN_SELL"}]),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    result = run_live_cycle({"symbols": ["BTCUSD"], "submit_orders": True}, runtime_state=runtime_state)

    assert calls == [False]
    assert result.iloc[0]["execution_status"] == "DUPLICATE_SUPPRESSED"
    assert bool(result.iloc[0]["order_submitted"]) is False
    assert runtime_state["BTCUSD"]["last_order_timestamp"] == "2026-04-25T12:00:10+00:00"
    assert runtime_state["BTCUSD"]["pyramid_count"] == 1


def test_run_live_cycle_does_not_suppress_duplicate_when_bar_timestamp_missing(monkeypatch):
    runtime_state = {
        "BTCUSD": {
            "last_processed_bar_timestamp": "2026-04-25T12:00:00+00:00",
            "last_signal": "BUY",
            "last_action": "BUY_SUBMITTED",
            "last_order_timestamp": "2026-04-25T12:00:10+00:00",
            "pyramid_count": 1,
        }
    }
    calls: list[bool] = []

    def fake_run_engine_bundle(config):
        calls.append(bool(config.get("submit_orders", False)))
        return {
            "market_data_df": pd.DataFrame(),
            "summary_df": pd.DataFrame(
                [
                    {
                        "symbol": config["symbol"],
                        "execution_status": "accepted" if bool(config.get("submit_orders", False)) else "DRY_RUN",
                        "signal": "BUY",
                        "action": "BUY_SUBMITTED" if bool(config.get("submit_orders", False)) else "DRY_RUN_BUY",
                        "order_submitted": bool(config.get("submit_orders", False)),
                    }
                ]
            ),
            "signal_df": pd.DataFrame(
                [
                    {
                        "signal": "BUY",
                        "action": "BUY_SUBMITTED" if bool(config.get("submit_orders", False)) else "DRY_RUN_BUY",
                    }
                ]
            ),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    result = run_live_cycle({"symbols": ["BTCUSD"], "submit_orders": True}, runtime_state=runtime_state)

    assert calls == [False, True]
    assert result.iloc[0]["execution_status"] == "accepted"
    assert bool(result.iloc[0]["order_submitted"]) is True
    assert runtime_state["BTCUSD"]["last_processed_bar_timestamp"] == "2026-04-25T12:00:00+00:00"


def test_run_live_cycle_resets_pyramid_count_after_successful_sell_close(monkeypatch):
    runtime_state = {
        "BTCUSD": {
            "last_processed_bar_timestamp": "2026-04-25T11:55:00+00:00",
            "last_signal": "BUY",
            "last_action": "BUY_SUBMITTED",
            "last_order_timestamp": "2026-04-25T11:55:05+00:00",
            "pyramid_count": 2,
        }
    }
    calls: list[bool] = []

    def fake_run_engine_bundle(config):
        calls.append(bool(config.get("submit_orders", False)))
        return {
            "market_data_df": pd.DataFrame([{"timestamp": "2026-04-25T12:00:00+00:00"}]),
            "summary_df": pd.DataFrame(
                [
                    {
                        "symbol": config["symbol"],
                        "execution_status": "accepted",
                        "signal": "SELL",
                        "action": "SELL_SUBMITTED",
                        "order_submitted": True,
                    }
                ]
            ),
            "signal_df": pd.DataFrame([{"signal": "SELL", "action": "SELL_SUBMITTED"}]),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    run_live_cycle({"symbols": ["BTCUSD"], "submit_orders": True}, runtime_state=runtime_state)

    assert calls == [False, True]
    assert runtime_state["BTCUSD"]["last_processed_bar_timestamp"] == "2026-04-25T12:00:00+00:00"
    assert runtime_state["BTCUSD"]["last_signal"] == "SELL"
    assert runtime_state["BTCUSD"]["last_action"] == "SELL_SUBMITTED"
    assert runtime_state["BTCUSD"]["pyramid_count"] == 0


def test_build_symbol_config_overrides_symbol_without_mutating_base_config():
    config = {"symbols": ["BTCUSD", "ETHUSD"], "symbol": "SPY", "qty": 0.001}

    symbol_config = build_symbol_config(config, "ETHUSD")

    assert symbol_config["symbol"] == "ETHUSD"
    assert config["symbol"] == "SPY"


def test_run_live_cycle_preserves_summary_fields_and_falls_back_for_empty_summary(monkeypatch):
    def fake_run_engine_bundle(config):
        assert "runtime_state" in config
        if config["symbol"] == "ETHUSD":
            return {
                "summary_df": pd.DataFrame(),
                "signal_df": pd.DataFrame([{"signal": "DO_NOTHING", "action": "NO_SIGNAL"}]),
            }
        return {
            "summary_df": pd.DataFrame(
                [
                    {
                        "symbol": config["symbol"],
                        "execution_status": "NO_ACTION",
                        "signal": "DO_NOTHING",
                        "action": "NO_SIGNAL",
                        "order_submitted": False,
                    }
                ]
            ),
            "signal_df": pd.DataFrame([{"signal": "DO_NOTHING", "action": "NO_SIGNAL"}]),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    result = run_live_cycle(
        {
            "symbols": ["BTCUSD", "ETHUSD"],
        },
        runtime_state={
            "BTCUSD": {
                "last_processed_bar_timestamp": "",
                "last_signal": "",
                "last_action": "",
                "last_order_timestamp": "",
                "pyramid_count": 0,
            },
            "ETHUSD": {
                "last_processed_bar_timestamp": "",
                "last_signal": "",
                "last_action": "",
                "last_order_timestamp": "",
                "pyramid_count": 0,
            },
        },
    )

    assert list(result["symbol"]) == ["BTCUSD", "ETHUSD"]
    assert result.iloc[0].to_dict() == {
        "symbol": "BTCUSD",
        "execution_status": "NO_ACTION",
        "signal": "DO_NOTHING",
        "action": "NO_SIGNAL",
        "order_submitted": False,
    }
    assert result.iloc[1]["symbol"] == "ETHUSD"
    assert result.iloc[1]["execution_status"] == "NO_SUMMARY"
    assert pd.isna(result.iloc[1]["signal"])
    assert pd.isna(result.iloc[1]["action"])
    assert pd.isna(result.iloc[1]["order_submitted"])


def test_pyramiding_limit_is_not_applicable_for_non_buy_signals():
    signal_df = pd.DataFrame([{"symbol": "BTCUSD", "signal": "SELL", "should_submit_order": True}])
    positions_df = pd.DataFrame()
    orders_df = pd.DataFrame()
    config = {
        "symbol": "BTCUSD",
        "runtime_state": {"BTCUSD": {"pyramid_count": 2}},
        "risk_params": {"max_pyramids": 3},
    }

    result = RISK_RULE_REGISTRY["pyramiding_limit"](signal_df, positions_df, orders_df, config)

    assert bool(result.iloc[0]["ok"]) is True
    assert result.iloc[0]["reason"] == "NOT_APPLICABLE"


def test_max_position_rule_is_not_applicable_for_non_buy_signals():
    signal_df = pd.DataFrame([{"symbol": "BTCUSD", "signal": "DO_NOTHING", "should_submit_order": False}])
    positions_df = pd.DataFrame([{"symbol": "BTCUSD", "qty": 100}])
    orders_df = pd.DataFrame()
    config = {
        "symbol": "BTCUSD",
        "qty": 0.001,
        "risk_params": {"max_position_qty": 0.0015},
    }

    result = RISK_RULE_REGISTRY["max_position"](signal_df, positions_df, orders_df, config)

    assert bool(result.iloc[0]["ok"]) is True
    assert result.iloc[0]["reason"] == "NOT_APPLICABLE"


def test_pyramiding_limit_blocks_when_max_pyramids_reached():
    signal_df = pd.DataFrame([{"symbol": "BTCUSD", "signal": "BUY", "should_submit_order": True}])
    positions_df = pd.DataFrame()
    orders_df = pd.DataFrame()
    config = {
        "symbol": "BTCUSD",
        "runtime_state": {"BTCUSD": {"pyramid_count": 3}},
        "risk_params": {"max_pyramids": 3},
    }

    result = RISK_RULE_REGISTRY["pyramiding_limit"](signal_df, positions_df, orders_df, config)

    assert bool(result.iloc[0]["ok"]) is False
    assert result.iloc[0]["reason"] == "MAX_PYRAMIDS_REACHED"


def test_max_position_rule_enforces_fractional_quantity_caps():
    signal_df = pd.DataFrame([{"symbol": "BTCUSD", "signal": "BUY", "should_submit_order": True}])
    positions_df = pd.DataFrame([{"symbol": "BTCUSD", "qty": 0.001}])
    orders_df = pd.DataFrame()
    config = {
        "symbol": "BTCUSD",
        "qty": 0.001,
        "risk_params": {"max_position_qty": 0.0015},
    }

    result = RISK_RULE_REGISTRY["max_position"](signal_df, positions_df, orders_df, config)

    assert bool(result.iloc[0]["ok"]) is False
    assert "position cap exceeded" in result.iloc[0]["reason"]


def test_execution_handler_blocks_short_signal_for_long_only_profile():
    signal_df = pd.DataFrame(
        [
            {
                "signal": "SELL_SHORT",
                "action": "RSI_CROSSED_BACK_BELOW_OVERBOUGHT",
                "should_submit_order": True,
            }
        ]
    )
    config = {
        "symbol": "BTCUSD",
        "submit_orders": True,
        "capability_profile": "alpaca_crypto_long_only",
    }

    result = alpaca_paper_execution_handler(signal_df, config)

    assert bool(result.iloc[0]["ok"]) is False
    assert bool(result.iloc[0]["order_submitted"]) is False
    assert result.iloc[0]["order_id"] == ""
    assert result.iloc[0]["status"] == "UNSUPPORTED_ACTION"
    assert result.iloc[0]["symbol"] == "BTCUSD"
    assert result.iloc[0]["action"] == "SELL_SHORT"


def test_execution_handler_returns_sell_dry_run_for_supported_close_action():
    signal_df = pd.DataFrame(
        [
            {
                "signal": "SELL",
                "action": "RSI_CROSSED_ABOVE_EXIT",
                "should_submit_order": True,
            }
        ]
    )
    config = {
        "symbol": "BTCUSD",
        "qty": 0.001,
        "submit_orders": False,
        "capability_profile": "alpaca_crypto_long_only",
    }

    result = alpaca_paper_execution_handler(signal_df, config)

    assert bool(result.iloc[0]["ok"]) is True
    assert bool(result.iloc[0]["order_submitted"]) is False
    assert result.iloc[0]["status"] == "DRY_RUN"
    assert result.iloc[0]["symbol"] == "BTCUSD"
    assert result.iloc[0]["action"] == "DRY_RUN_SELL"


def test_execution_handler_submits_sell_using_live_position_qty(monkeypatch):
    captured: dict[str, object] = {}

    def fake_get_positions_df():
        return pd.DataFrame([{"symbol": "BTC/USD", "qty": "0.003"}])

    def fake_submit_market_order_df(symbol: str, qty: float, side: str):
        captured["symbol"] = symbol
        captured["qty"] = qty
        captured["side"] = side
        return pd.DataFrame(
            [
                {
                    "ok": True,
                    "order_id": "sell-order-1",
                    "status": "accepted",
                    "symbol": symbol,
                }
            ]
        )

    import alpaca_engine

    monkeypatch.setattr(alpaca_engine, "get_positions_df", fake_get_positions_df)
    monkeypatch.setattr(alpaca_engine, "submit_market_order_df", fake_submit_market_order_df)

    signal_df = pd.DataFrame(
        [
            {
                "signal": "SELL",
                "action": "RSI_CROSSED_ABOVE_EXIT",
                "should_submit_order": True,
            }
        ]
    )
    config = {
        "symbol": "BTCUSD",
        "qty": 0.001,
        "submit_orders": True,
        "capability_profile": "alpaca_crypto_long_only",
    }

    result = alpaca_paper_execution_handler(signal_df, config)

    assert captured == {"symbol": "BTCUSD", "qty": 0.003, "side": "sell"}
    assert bool(result.iloc[0]["ok"]) is True
    assert bool(result.iloc[0]["order_submitted"]) is True
    assert result.iloc[0]["status"] == "accepted"
    assert result.iloc[0]["action"] == "SELL_SUBMITTED"
