import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pandas as pd


def normalize_control_paths() -> dict[str, Path]:
    logs_dir = Path("logs")
    return {
        "pid_path": logs_dir / "live_runner.pid",
        "config_path": logs_dir / "live_runner_config.json",
        "log_path": logs_dir / "live_runner_log.csv",
    }


def read_live_log_df(log_path=None, tail_rows=None) -> pd.DataFrame:
    path = Path(log_path) if log_path is not None else normalize_control_paths()["log_path"]
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()

    df = pd.read_csv(path)
    if tail_rows is not None:
        df = df.tail(tail_rows).reset_index(drop=True)
    return df


def _resolve_control_path(path_value, key: str) -> Path:
    return Path(path_value) if path_value is not None else normalize_control_paths()[key]


def _read_pid(pid_path: Path) -> int | None:
    metadata = _read_pid_metadata(pid_path)
    if metadata is None:
        return None
    return metadata.get("pid")


def _read_pid_metadata(pid_path: Path) -> dict | None:
    if not pid_path.exists():
        return None

    raw_value = pid_path.read_text().strip()
    if not raw_value:
        return None

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        try:
            return {"pid": int(raw_value)}
        except ValueError:
            return None

    if isinstance(parsed, int):
        return {"pid": parsed}
    if not isinstance(parsed, dict):
        return None

    pid_value = parsed.get("pid")
    try:
        parsed["pid"] = int(pid_value)
    except (TypeError, ValueError):
        return None
    return parsed


def _is_pid_active(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_process_cmdline(pid: int) -> list[str]:
    cmdline_path = Path("/proc") / str(pid) / "cmdline"
    try:
        raw_value = cmdline_path.read_text()
    except OSError:
        return []
    return [part for part in raw_value.split("\x00") if part]


def _normalize_path_text(path_value) -> str | None:
    if path_value in (None, ""):
        return None
    return str(Path(path_value).resolve())


def _cmdline_contains_path(cmdline: list[str], expected_path) -> bool:
    normalized_expected = _normalize_path_text(expected_path)
    if normalized_expected is None:
        return False

    normalized_cmdline = {_normalize_path_text(part) for part in cmdline}
    return normalized_expected in normalized_cmdline


def _is_live_runner_pid(pid: int | None, *, pid_metadata: dict | None = None, config_path=None, run_live_path=None) -> bool:
    if not _is_pid_active(pid):
        return False

    metadata = pid_metadata or {}
    expected_run_live_path = metadata.get("run_live_path", run_live_path)
    expected_config_path = metadata.get("config_path", config_path)
    if expected_run_live_path in (None, ""):
        return False

    cmdline = _read_process_cmdline(pid)
    if not cmdline or not _cmdline_contains_path(cmdline, expected_run_live_path):
        return False
    if expected_config_path not in (None, "") and not _cmdline_contains_path(cmdline, expected_config_path):
        return False
    return True


def _build_runner_status_df(
    *,
    status: str,
    pid_path: Path,
    config_path: Path,
    log_path: Path,
    pid: int | None = None,
    is_running: bool = False,
    started: bool = False,
    stopped: bool = False,
    config_written: bool = False,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "status": status,
                "is_running": bool(is_running),
                "started": bool(started),
                "stopped": bool(stopped),
                "config_written": bool(config_written),
                "pid": pid,
                "pid_path": str(pid_path),
                "config_path": str(config_path),
                "log_path": str(log_path),
            }
        ]
    )


def get_live_runner_status_df(pid_path=None, config_path=None, log_path=None) -> pd.DataFrame:
    resolved_pid_path = _resolve_control_path(pid_path, "pid_path")
    resolved_config_path = _resolve_control_path(config_path, "config_path")
    resolved_log_path = _resolve_control_path(log_path, "log_path")
    pid_metadata = _read_pid_metadata(resolved_pid_path)
    pid = None if pid_metadata is None else pid_metadata.get("pid")

    if not resolved_pid_path.exists() or pid is None:
        return _build_runner_status_df(
            status="NOT_RUNNING",
            pid_path=resolved_pid_path,
            config_path=resolved_config_path,
            log_path=resolved_log_path,
            pid=pid,
        )

    if _is_live_runner_pid(
        pid,
        pid_metadata=pid_metadata,
        config_path=resolved_config_path,
        run_live_path=Path(__file__).with_name("run_live.py"),
    ):
        return _build_runner_status_df(
            status="RUNNING",
            pid_path=resolved_pid_path,
            config_path=resolved_config_path,
            log_path=resolved_log_path,
            pid=pid,
            is_running=True,
        )

    if _is_pid_active(pid):
        return _build_runner_status_df(
            status="PID_MISMATCH",
            pid_path=resolved_pid_path,
            config_path=resolved_config_path,
            log_path=resolved_log_path,
            pid=pid,
        )

    return _build_runner_status_df(
        status="STALE_PID",
        pid_path=resolved_pid_path,
        config_path=resolved_config_path,
        log_path=resolved_log_path,
        pid=pid,
    )


def start_live_runner(
    live_config: dict,
    *,
    pid_path=None,
    config_path=None,
    log_path=None,
    run_live_path=None,
    python_executable=None,
    popen_factory=None,
) -> pd.DataFrame:
    resolved_pid_path = _resolve_control_path(pid_path, "pid_path")
    resolved_config_path = _resolve_control_path(config_path, "config_path")
    resolved_log_path = _resolve_control_path(log_path, "log_path")
    current_status_df = get_live_runner_status_df(
        pid_path=resolved_pid_path,
        config_path=resolved_config_path,
        log_path=resolved_log_path,
    )

    if current_status_df.loc[0, "status"] == "RUNNING":
        current_status_df.loc[0, "status"] = "ALREADY_RUNNING"
        return current_status_df

    if resolved_pid_path.exists():
        resolved_pid_path.unlink()

    payload = dict(live_config)
    payload.setdefault("live_log_path", str(resolved_log_path))
    payload.setdefault("pid_path", str(resolved_pid_path))
    resolved_config_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_config_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    command = [
        python_executable or sys.executable,
        str(Path(run_live_path) if run_live_path is not None else Path(__file__).with_name("run_live.py")),
        str(resolved_config_path),
    ]
    launcher = popen_factory or subprocess.Popen
    launcher(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return _build_runner_status_df(
        status="STARTING",
        pid_path=resolved_pid_path,
        config_path=resolved_config_path,
        log_path=resolved_log_path,
        started=True,
        config_written=True,
    )


def stop_live_runner(pid_path=None, config_path=None, log_path=None) -> pd.DataFrame:
    resolved_pid_path = _resolve_control_path(pid_path, "pid_path")
    resolved_config_path = _resolve_control_path(config_path, "config_path")
    resolved_log_path = _resolve_control_path(log_path, "log_path")
    pid_metadata = _read_pid_metadata(resolved_pid_path)
    pid = None if pid_metadata is None else pid_metadata.get("pid")

    if not resolved_pid_path.exists() or pid is None:
        if resolved_pid_path.exists():
            resolved_pid_path.unlink()
        return _build_runner_status_df(
            status="NOT_RUNNING",
            pid_path=resolved_pid_path,
            config_path=resolved_config_path,
            log_path=resolved_log_path,
        )

    if _is_live_runner_pid(
        pid,
        pid_metadata=pid_metadata,
        config_path=resolved_config_path,
        run_live_path=Path(__file__).with_name("run_live.py"),
    ):
        os.kill(pid, signal.SIGTERM)
        resolved_pid_path.unlink(missing_ok=True)
        return _build_runner_status_df(
            status="STOPPED",
            pid_path=resolved_pid_path,
            config_path=resolved_config_path,
            log_path=resolved_log_path,
            pid=pid,
            stopped=True,
        )

    if _is_pid_active(pid):
        resolved_pid_path.unlink(missing_ok=True)
        return _build_runner_status_df(
            status="PID_MISMATCH",
            pid_path=resolved_pid_path,
            config_path=resolved_config_path,
            log_path=resolved_log_path,
            pid=pid,
        )

    if not _is_pid_active(pid):
        resolved_pid_path.unlink(missing_ok=True)
        return _build_runner_status_df(
            status="STALE_PID",
            pid_path=resolved_pid_path,
            config_path=resolved_config_path,
            log_path=resolved_log_path,
            pid=pid,
        )
