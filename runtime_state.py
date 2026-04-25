"""Helpers for in-memory live runtime state."""

from datetime import datetime, timezone


def build_initial_state(symbols: list[str]) -> dict[str, dict]:
    return {
        symbol: {
            "last_processed_bar_timestamp": "",
            "last_signal": "",
            "last_action": "",
            "last_order_timestamp": "",
            "pyramid_count": 0,
        }
        for symbol in symbols
    }


def should_suppress_duplicate_action(
    symbol_state: dict,
    current_bar_timestamp: str,
    current_signal: str,
    current_action: str,
) -> bool:
    if current_bar_timestamp == "":
        return False

    return (
        current_signal != ""
        and symbol_state.get("last_processed_bar_timestamp", "") == current_bar_timestamp
        and symbol_state.get("last_signal", "") == current_signal
    )


def update_symbol_state(
    symbol_state: dict,
    current_bar_timestamp: str,
    current_signal: str,
    current_action: str,
    order_submitted: bool,
    pyramid_increment: int,
) -> dict:
    updated = dict(symbol_state)
    if current_bar_timestamp != "":
        updated["last_processed_bar_timestamp"] = current_bar_timestamp
    updated["last_signal"] = current_signal
    updated["last_action"] = current_action
    if order_submitted:
        updated["last_order_timestamp"] = datetime.now(timezone.utc).isoformat()
    if order_submitted and current_signal == "SELL":
        updated["pyramid_count"] = 0
    else:
        updated["pyramid_count"] = int(updated.get("pyramid_count", 0)) + int(pyramid_increment)
    return updated
