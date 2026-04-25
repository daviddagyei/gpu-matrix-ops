import json
from pathlib import Path


def test_trade_notebook_has_engine_workflow_cells():
    notebook_path = Path("trade.ipynb")
    notebook = json.loads(notebook_path.read_text())

    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 5

    code_sources = [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    notebook_source = "\n".join(code_sources)

    assert "from engine import run_engine_bundle" in notebook_source
    assert "engine_config =" in notebook_source
    assert "\"preset\": \"alpaca_sma_default\"" in notebook_source
    assert "\"timeframe\":" in notebook_source
    assert "bundle = run_engine_bundle(engine_config)" in notebook_source
    assert "settings_df = bundle[\"settings_df\"]" in notebook_source
    assert "market_data_df = bundle[\"market_data_df\"]" in notebook_source
    assert "signal_df = bundle[\"signal_df\"]" in notebook_source
    assert "risk_df = bundle[\"risk_df\"]" in notebook_source
    assert "execution_df = bundle[\"execution_df\"]" in notebook_source
    assert "submit_orders = False" in notebook_source


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
