import json
import os
import sys
from pathlib import Path

from live_runner import run_live_loop


DEFAULT_LIVE_CONFIG = {"preset": "alpaca_rsi_scalp_live", "submit_orders": True}


def load_live_config(config_path=None) -> dict:
    if config_path is None:
        return dict(DEFAULT_LIVE_CONFIG)

    return json.loads(Path(config_path).read_text())


def write_pid_file(pid_path, *, config_path=None, run_live_path=None) -> Path:
    resolved_pid_path = Path(pid_path)
    resolved_pid_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "config_path": None if config_path is None else str(Path(config_path).resolve()),
        "run_live_path": str(
            (Path(run_live_path) if run_live_path is not None else Path(__file__)).resolve()
        ),
    }
    resolved_pid_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return resolved_pid_path


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    config_path = args[0] if args else None
    config = load_live_config(config_path)
    pid_path = config.get("pid_path", Path("logs") / "live_runner.pid")
    resolved_pid_path = write_pid_file(pid_path, config_path=config_path, run_live_path=Path(__file__))

    try:
        run_live_loop(config)
    finally:
        resolved_pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
