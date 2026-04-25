import json
from pathlib import Path

import pandas as pd
import pytest

from live_runner import append_live_runner_log, run_live_cycle
from notebook_controls import (
    get_live_runner_status_df,
    normalize_control_paths,
    read_live_log_df,
    start_live_runner,
    stop_live_runner,
)


def test_append_live_runner_log_writes_csv_row(tmp_path: Path):
    log_path = tmp_path / "live_runner_log.csv"
    summary_df = pd.DataFrame(
        [
            {
                "symbol": "BTCUSD",
                "execution_status": "NO_ACTION",
                "signal": "BUY",
                "action": "DRY_RUN_BUY",
                "order_submitted": False,
            }
        ]
    )
    symbol_state = {
        "last_processed_bar_timestamp": "2026-04-25T12:00:00+00:00",
        "pyramid_count": 1,
    }

    append_live_runner_log(
        log_path=log_path,
        summary_df=summary_df,
        config={"timeframe": "5Min", "strategy": "rsi_mean_reversion_scalp"},
        symbol_state=symbol_state,
    )

    result = pd.read_csv(log_path)

    assert list(result["symbol"]) == ["BTCUSD"]
    assert list(result["strategy"]) == ["rsi_mean_reversion_scalp"]
    assert list(result["timeframe"]) == ["5Min"]
    assert list(result["last_processed_bar_timestamp"]) == ["2026-04-25T12:00:00+00:00"]
    assert list(result["pyramid_count"]) == [1]
    assert "timestamp_utc" in result.columns


def test_run_live_cycle_appends_log_row_when_log_path_present(monkeypatch, tmp_path: Path):
    log_path = tmp_path / "live_runner_log.csv"
    runtime_state = {
        "BTCUSD": {
            "last_processed_bar_timestamp": "",
            "last_signal": "",
            "last_action": "",
            "last_order_timestamp": "",
            "pyramid_count": 0,
        }
    }

    def fake_run_engine_bundle(config):
        return {
            "market_data_df": pd.DataFrame([{"timestamp": "2026-04-25T12:00:00+00:00"}]),
            "summary_df": pd.DataFrame(
                [
                    {
                        "symbol": "BTCUSD",
                        "execution_status": "NO_ACTION",
                        "signal": "BUY",
                        "action": "DRY_RUN_BUY",
                        "order_submitted": False,
                    }
                ]
            ),
            "signal_df": pd.DataFrame([{"signal": "BUY", "action": "DRY_RUN_BUY"}]),
        }

    monkeypatch.setattr("live_runner.run_engine_bundle", fake_run_engine_bundle)

    run_live_cycle(
        {
            "symbols": ["BTCUSD"],
            "strategy": "rsi_mean_reversion_scalp",
            "timeframe": "5Min",
            "live_log_path": str(log_path),
        },
        runtime_state=runtime_state,
    )

    result = pd.read_csv(log_path)

    assert list(result["symbol"]) == ["BTCUSD"]
    assert list(result["strategy"]) == ["rsi_mean_reversion_scalp"]
    assert list(result["timeframe"]) == ["5Min"]


def test_normalize_control_paths_returns_pid_config_and_log_paths():
    paths = normalize_control_paths()

    assert "pid_path" in paths
    assert "config_path" in paths
    assert "log_path" in paths
    assert paths["pid_path"].parent.name == "logs"
    assert paths["config_path"].parent.name == "logs"
    assert paths["log_path"].parent.name == "logs"


def test_read_live_log_df_returns_dataframe_for_existing_log(tmp_path: Path):
    log_path = tmp_path / "live_runner_log.csv"
    log_path.write_text("timestamp_utc,symbol\n2026-04-25T12:00:00+00:00,BTCUSD\n")

    df = read_live_log_df(log_path=log_path)

    assert list(df["symbol"]) == ["BTCUSD"]


def test_read_live_log_df_uses_default_logs_path(monkeypatch, tmp_path: Path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    default_log_path = logs_dir / "live_runner_log.csv"
    default_log_path.write_text(
        "timestamp_utc,symbol\n"
        "2026-04-25T12:00:00+00:00,BTCUSD\n"
    )
    monkeypatch.chdir(tmp_path)

    df = read_live_log_df()

    assert list(df["symbol"]) == ["BTCUSD"]


def test_read_live_log_df_trims_tail_rows(tmp_path: Path):
    log_path = tmp_path / "live_runner_log.csv"
    log_path.write_text(
        "timestamp_utc,symbol\n"
        "2026-04-25T12:00:00+00:00,BTCUSD\n"
        "2026-04-25T12:01:00+00:00,ETHUSD\n"
        "2026-04-25T12:02:00+00:00,SOLUSD\n"
    )

    df = read_live_log_df(log_path=log_path, tail_rows=2)

    assert list(df["symbol"]) == ["ETHUSD", "SOLUSD"]


def test_get_live_runner_status_df_reports_missing_pid_file(tmp_path: Path):
    pid_path = tmp_path / "live_runner.pid"

    df = get_live_runner_status_df(pid_path=pid_path)

    assert bool(df.loc[0, "is_running"]) is False
    assert df.loc[0, "status"] == "NOT_RUNNING"


def test_start_live_runner_refuses_duplicate_when_pid_is_active(monkeypatch, tmp_path: Path):
    pid_path = tmp_path / "live_runner.pid"
    config_path = tmp_path / "live_runner_config.json"
    log_path = tmp_path / "live_runner_log.csv"
    pid_path.write_text(
        json.dumps(
            {
                "pid": 4242,
                "config_path": str(config_path),
                "run_live_path": str(Path("run_live.py").resolve()),
            }
        )
    )
    popen_calls = []

    def fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        raise AssertionError("subprocess should not be launched when pid is active")

    monkeypatch.setattr("notebook_controls._is_live_runner_pid", lambda pid, **kwargs: pid == 4242)

    df = start_live_runner(
        {"symbols": ["BTCUSD"]},
        pid_path=pid_path,
        config_path=config_path,
        log_path=log_path,
        popen_factory=fake_popen,
    )

    assert df.loc[0, "status"] == "ALREADY_RUNNING"
    assert bool(df.loc[0, "started"]) is False
    assert int(df.loc[0, "pid"]) == 4242
    assert popen_calls == []


def test_get_live_runner_status_df_does_not_mark_unrelated_active_pid_as_running(monkeypatch, tmp_path: Path):
    pid_path = tmp_path / "live_runner.pid"
    config_path = tmp_path / "live_runner_config.json"
    pid_path.write_text(
        json.dumps(
            {
                "pid": 4242,
                "config_path": str(config_path),
                "run_live_path": str(Path("run_live.py").resolve()),
            }
        )
    )

    monkeypatch.setattr("notebook_controls._is_pid_active", lambda pid: pid == 4242)
    monkeypatch.setattr("notebook_controls._read_process_cmdline", lambda pid: ["/usr/bin/python3", "other_script.py"])

    df = get_live_runner_status_df(pid_path=pid_path, config_path=config_path)

    assert bool(df.loc[0, "is_running"]) is False
    assert df.loc[0, "status"] == "PID_MISMATCH"
    assert int(df.loc[0, "pid"]) == 4242


def test_stop_live_runner_does_not_terminate_unrelated_active_pid(monkeypatch, tmp_path: Path):
    pid_path = tmp_path / "live_runner.pid"
    config_path = tmp_path / "live_runner_config.json"
    pid_path.write_text(
        json.dumps(
            {
                "pid": 4242,
                "config_path": str(config_path),
                "run_live_path": str(Path("run_live.py").resolve()),
            }
        )
    )
    kill_calls = []

    def fake_kill(pid, sig):
        kill_calls.append((pid, sig))
        raise AssertionError("unrelated active pid must not be terminated")

    monkeypatch.setattr("notebook_controls.os.kill", fake_kill)
    monkeypatch.setattr("notebook_controls._is_pid_active", lambda pid: True)
    monkeypatch.setattr("notebook_controls._read_process_cmdline", lambda pid: ["/usr/bin/python3", "other_script.py"])

    df = stop_live_runner(pid_path=pid_path, config_path=config_path)

    assert df.loc[0, "status"] == "PID_MISMATCH"
    assert bool(df.loc[0, "stopped"]) is False
    assert kill_calls == []
    assert pid_path.exists() is False


@pytest.mark.parametrize(
    ("pid_contents", "expected_status"),
    [
        (None, "NOT_RUNNING"),
        ("4242", "STALE_PID"),
    ],
)
def test_stop_live_runner_handles_missing_or_stale_pid_file(
    monkeypatch, tmp_path: Path, pid_contents: str | None, expected_status: str
):
    pid_path = tmp_path / "live_runner.pid"
    if pid_contents is not None:
        pid_path.write_text(pid_contents)

    kill_calls = []

    def fake_kill(pid, sig):
        kill_calls.append((pid, sig))
        raise AssertionError("os.kill should not be called for missing or stale pid")

    monkeypatch.setattr("notebook_controls.os.kill", fake_kill)
    monkeypatch.setattr("notebook_controls._is_pid_active", lambda pid: False)

    df = stop_live_runner(pid_path=pid_path)

    assert df.loc[0, "status"] == expected_status
    assert bool(df.loc[0, "stopped"]) is False
    assert kill_calls == []
    assert pid_path.exists() is False
