import json
from pathlib import Path


def test_trade_notebook_has_engine_workflow_cells():
    notebook_path = Path("trade.ipynb")
    notebook = json.loads(notebook_path.read_text())

    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 8

    code_sources = [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    assert any("from notebook_controls import" in source for source in code_sources)
    assert any("from registry import resolve_engine_config" in source for source in code_sources)
    assert any("from strategies import STRATEGY_REGISTRY" in source for source in code_sources)
    assert any("available_strategies_df" in source for source in code_sources)

    config_cell = next(source for source in code_sources if "live_overrides =" in source)
    assert "\"preset\": \"alpaca_rsi_scalp_live\"" in config_cell
    assert "\"strategy\": \"rsi_mean_reversion_scalp\"" in config_cell
    assert "\"strategy_params\":" in config_cell
    assert "\"risk_params\":" in config_cell
    assert "\"symbols\": [\"BTCUSD\"]" in config_cell
    assert "\"poll_interval_seconds\": 30" in config_cell
    assert "\"submit_orders\":" in config_cell
    assert "\"max_pyramids\": 10" in config_cell
    assert "live_config = resolve_engine_config(live_overrides)" in config_cell

    assert any("normalize_control_paths()" in source for source in code_sources)
    assert any("start_live_runner(live_config)" in source for source in code_sources)
    assert any("get_live_runner_status_df()" in source for source in code_sources)
    assert any("read_live_log_df(tail_rows=100)" in source for source in code_sources)
    assert any("stop_live_runner()" in source for source in code_sources)


def test_backtest_notebook_has_rsi_backtest_workflow_cells():
    notebook_path = Path("backtest_rsi_scalp.ipynb")
    notebook = json.loads(notebook_path.read_text())

    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 5

    code_sources = [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    notebook_source = "\n".join(code_sources)

    assert "from backtesting_tools import build_backtest_bundle" in notebook_source
    assert "\"symbol\": \"BTCUSD\"" in notebook_source
    assert "\"timeframe\": \"5Min\"" in notebook_source
    assert "\"lookback_days\": 7" in notebook_source
    assert "bundle = build_backtest_bundle(config=backtest_config)" in notebook_source
    assert "metrics_df = bundle[\"metrics_df\"]" in notebook_source
    assert "trades_df = bundle[\"trades_df\"]" in notebook_source
    assert "equity_curve_df = bundle[\"equity_curve_df\"]" in notebook_source
