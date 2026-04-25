from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

try:
    from alpaca.data.enums import CryptoFeed, DataFeed
    from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
    from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
    from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest
except Exception:  # pragma: no cover - defensive import guard
    CryptoFeed = None
    DataFeed = None
    CryptoHistoricalDataClient = None
    StockHistoricalDataClient = None
    CryptoBarsRequest = None
    StockBarsRequest = None
    TimeFrame = None
    TimeFrameUnit = None
    TradingClient = None
    OrderSide = None
    QueryOrderStatus = None
    TimeInForce = None
    GetOrdersRequest = None
    MarketOrderRequest = None


_AUTO = object()

STANDARD_STATUS_COLUMNS = [
    "ok",
    "paper",
    "function_name",
    "timestamp_utc",
    "error_type",
    "error_message",
]

PRICE_DATA_COLUMNS = [
    "symbol",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "trade_count",
    "vwap",
    "sma20",
]

POSITION_COLUMNS = [
    "symbol",
    "qty",
    "side",
    "market_value",
    "avg_entry_price",
    "current_price",
    "unrealized_pl",
]

ORDER_COLUMNS = [
    "order_id",
    "symbol",
    "qty",
    "side",
    "type",
    "time_in_force",
    "status",
    "submitted_at",
]

CANCEL_COLUMNS = [
    "ok",
    "paper",
    "function_name",
    "timestamp_utc",
    "error_type",
    "error_message",
    "order_id",
    "symbol",
    "cancel_requested",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_status_df(function_name: str, paper: bool = True, **fields: Any) -> pd.DataFrame:
    row = {
        "ok": True,
        "paper": paper,
        "function_name": function_name,
        "timestamp_utc": _utc_now_iso(),
        "error_type": "",
        "error_message": "",
    }
    row.update(fields)
    return pd.DataFrame([row])


def _build_error_df(
    function_name: str,
    error_type: str,
    error_message: str,
    paper: bool = True,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ok": False,
                "paper": paper,
                "function_name": function_name,
                "timestamp_utc": _utc_now_iso(),
                "error_type": error_type,
                "error_message": error_message,
            }
        ]
    )


def _empty_df(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _stringify(value: Any) -> str:
    return "" if value is None else str(value)


def _load_credentials() -> tuple[str | None, str | None]:
    load_dotenv()
    return os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(" ", "")


def _canonicalize_crypto_symbol(symbol: str) -> str | None:
    normalized = _normalize_symbol(symbol)
    if not normalized:
        return None
    if "/" in normalized:
        parts = [part for part in normalized.split("/") if part]
        if len(parts) == 2 and all(parts):
            return f"{parts[0]}/{parts[1]}"
        return None
    if "-" in normalized:
        parts = [part for part in normalized.split("-") if part]
        if len(parts) == 2 and all(parts):
            return f"{parts[0]}/{parts[1]}"
        return None

    for quote in ("USDT", "USDC", "USD", "BTC", "ETH", "EUR"):
        if normalized.endswith(quote) and len(normalized) > len(quote):
            base = normalized[: -len(quote)]
            if len(base) >= 3:
                return f"{base}/{quote}"
    return None


def _is_crypto_symbol(symbol: str) -> bool:
    return _canonicalize_crypto_symbol(symbol) is not None


def _symbols_match(left: str, right: str) -> bool:
    left_crypto = _canonicalize_crypto_symbol(left)
    right_crypto = _canonicalize_crypto_symbol(right)
    if left_crypto or right_crypto:
        return left_crypto == right_crypto
    return _normalize_symbol(left) == _normalize_symbol(right)


def get_env_config() -> pd.DataFrame:
    api_key, secret_key = _load_credentials()
    if not api_key or not secret_key:
        return _build_error_df(
            function_name="get_env_config",
            error_type="MissingCredentials",
            error_message="ALPACA_API_KEY and ALPACA_SECRET_KEY are required",
        )

    return _build_status_df(
        "get_env_config",
        api_key_present=True,
        secret_key_present=True,
    )


def _resolve_trading_client(trading_client: Any, function_name: str):
    if TradingClient is None:
        return None, _build_error_df(
            function_name=function_name,
            error_type="MissingDependency",
            error_message="alpaca-py is not available",
        )
    if trading_client is None:
        return None, _build_error_df(
            function_name=function_name,
            error_type="MissingClient",
            error_message="TradingClient is required",
        )
    if trading_client is not _AUTO:
        return trading_client, None

    api_key, secret_key = _load_credentials()
    if not api_key or not secret_key:
        return None, _build_error_df(
            function_name=function_name,
            error_type="MissingCredentials",
            error_message="ALPACA_API_KEY and ALPACA_SECRET_KEY are required",
        )

    try:
        return TradingClient(api_key=api_key, secret_key=secret_key, paper=True), None
    except Exception as exc:  # pragma: no cover - network/auth path
        return None, _build_error_df(
            function_name=function_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def _resolve_data_client(data_client: Any, function_name: str):
    if StockHistoricalDataClient is None:
        return None, _build_error_df(
            function_name=function_name,
            error_type="MissingDependency",
            error_message="alpaca-py is not available",
        )
    if data_client is None:
        return None, _build_error_df(
            function_name=function_name,
            error_type="MissingClient",
            error_message="StockHistoricalDataClient is required",
        )
    if data_client is not _AUTO:
        return data_client, None

    api_key, secret_key = _load_credentials()
    if not api_key or not secret_key:
        return None, _build_error_df(
            function_name=function_name,
            error_type="MissingCredentials",
            error_message="ALPACA_API_KEY and ALPACA_SECRET_KEY are required",
        )

    try:
        return StockHistoricalDataClient(api_key=api_key, secret_key=secret_key), None
    except Exception as exc:  # pragma: no cover - network/auth path
        return None, _build_error_df(
            function_name=function_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def _resolve_crypto_data_client(crypto_data_client: Any, function_name: str):
    if CryptoHistoricalDataClient is None:
        return None, _build_error_df(
            function_name=function_name,
            error_type="MissingDependency",
            error_message="alpaca-py crypto market-data support is not available",
        )
    if crypto_data_client is None:
        return None, _build_error_df(
            function_name=function_name,
            error_type="MissingClient",
            error_message="CryptoHistoricalDataClient is required",
        )
    if crypto_data_client is not _AUTO:
        return crypto_data_client, None

    api_key, secret_key = _load_credentials()
    try:
        return CryptoHistoricalDataClient(api_key=api_key, secret_key=secret_key), None
    except Exception as exc:  # pragma: no cover - network/auth path
        return None, _build_error_df(
            function_name=function_name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def _timeframe_from_string(timeframe: str):
    if TimeFrame is None:
        return None
    timeframe_map = {
        "1DAY": TimeFrame.Day,
        "1HOUR": TimeFrame.Hour,
        "1MIN": TimeFrame.Minute,
        "5MIN": TimeFrame(5, TimeFrameUnit.Minute),
        "15MIN": TimeFrame(15, TimeFrameUnit.Minute),
        "30MIN": TimeFrame(30, TimeFrameUnit.Minute),
    }
    normalized = timeframe.strip().upper()
    if normalized in timeframe_map:
        return timeframe_map[normalized]
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def _normalize_price_frame(raw_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if raw_df.empty:
        return _empty_df(PRICE_DATA_COLUMNS)

    df = raw_df.copy().reset_index()
    if "symbol" not in df.columns:
        df["symbol"] = symbol
    if "timestamp" not in df.columns:
        if "index" in df.columns:
            df = df.rename(columns={"index": "timestamp"})
        elif "level_1" in df.columns:
            df = df.rename(columns={"level_1": "timestamp"})
    if "symbol" in df.columns:
        df = df[df["symbol"] == symbol]

    for column in PRICE_DATA_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.sort_values("timestamp")
    df["sma20"] = pd.to_numeric(df["close"], errors="coerce").rolling(20).mean()
    return df[PRICE_DATA_COLUMNS].reset_index(drop=True)


def _fetch_stock_price_data_df(
    symbol: str,
    lookback_days: int,
    timeframe: str,
    data_client: Any,
) -> pd.DataFrame:
    client, error_df = _resolve_data_client(data_client, "get_price_data_df")
    if error_df is not None:
        return error_df

    try:
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=_timeframe_from_string(timeframe),
            start=datetime.now(timezone.utc) - timedelta(days=lookback_days),
            end=datetime.now(timezone.utc),
            feed=DataFeed.IEX if DataFeed is not None else None,
        )
        raw_bars = client.get_stock_bars(request)
        raw_df = raw_bars.df.copy() if hasattr(raw_bars, "df") else pd.DataFrame(raw_bars)
        return _normalize_price_frame(raw_df, symbol)
    except Exception as exc:  # pragma: no cover - network/auth path
        return _build_error_df(
            function_name="get_price_data_df",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def _fetch_crypto_price_data_df(
    symbol: str,
    lookback_days: int,
    timeframe: str,
    crypto_data_client: Any,
) -> pd.DataFrame:
    client, error_df = _resolve_crypto_data_client(crypto_data_client, "get_price_data_df")
    if error_df is not None:
        return error_df

    try:
        request = CryptoBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=_timeframe_from_string(timeframe),
            start=datetime.now(timezone.utc) - timedelta(days=lookback_days),
            end=datetime.now(timezone.utc),
        )
        raw_bars = client.get_crypto_bars(
            request,
            feed=CryptoFeed.US if CryptoFeed is not None else None,
        )
        raw_df = raw_bars.df.copy() if hasattr(raw_bars, "df") else pd.DataFrame(raw_bars)
        return _normalize_price_frame(raw_df, symbol)
    except Exception as exc:  # pragma: no cover - network/auth path
        return _build_error_df(
            function_name="get_price_data_df",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def normalize_order_response_df(order: Any, paper: bool = True) -> pd.DataFrame:
    return _build_status_df(
        "normalize_order_response_df",
        paper=paper,
        order_id=_stringify(getattr(order, "id", "")),
        symbol=_stringify(getattr(order, "symbol", "")),
        qty=_stringify(getattr(order, "qty", "")),
        side=_stringify(getattr(order, "side", "")),
        type=_stringify(getattr(order, "type", "")),
        time_in_force=_stringify(getattr(order, "time_in_force", "")),
        status=_stringify(getattr(order, "status", "")),
        submitted_at=_stringify(getattr(order, "submitted_at", "")),
    )


def _extract_order_row(order: Any) -> dict[str, Any]:
    return {
        "order_id": _stringify(getattr(order, "id", "")),
        "symbol": _stringify(getattr(order, "symbol", "")),
        "qty": _stringify(getattr(order, "qty", "")),
        "side": _stringify(getattr(order, "side", "")),
        "type": _stringify(getattr(order, "type", "")),
        "time_in_force": _stringify(getattr(order, "time_in_force", "")),
        "status": _stringify(getattr(order, "status", "")),
        "submitted_at": _stringify(getattr(order, "submitted_at", "")),
    }


def append_trade_log_row(row: dict, log_path: str | Path = "logs/trade_log.csv") -> pd.DataFrame:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([row])
    if path.exists():
        frame.to_csv(path, mode="a", header=False, index=False)
    else:
        frame.to_csv(path, index=False)
    return frame


def enforce_max_position_size(
    symbol: str,
    current_qty: int,
    requested_qty: int,
    max_position_qty: int,
) -> pd.DataFrame:
    total_qty = current_qty + requested_qty
    if total_qty > max_position_qty:
        return _build_error_df(
            function_name="enforce_max_position_size",
            error_type="RiskCheckFailed",
            error_message=f"{symbol} position cap exceeded",
        )

    return _build_status_df(
        "enforce_max_position_size",
        symbol=symbol,
        current_qty=current_qty,
        requested_qty=requested_qty,
        max_position_qty=max_position_qty,
    )


def evaluate_sma_signal_row(
    symbol: str,
    qty: int,
    latest_close: float,
    latest_sma20: float,
    has_position: bool,
) -> pd.DataFrame:
    is_buy_signal = latest_close > latest_sma20
    should_submit_order = is_buy_signal and not has_position
    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "qty": qty,
                "close": latest_close,
                "sma20": latest_sma20,
                "has_position": has_position,
                "signal": "BUY" if is_buy_signal else "DO_NOTHING",
                "should_submit_order": should_submit_order,
            }
        ]
    )


def get_account_df(trading_client: Any = _AUTO) -> pd.DataFrame:
    client, error_df = _resolve_trading_client(trading_client, "get_account_df")
    if error_df is not None:
        return error_df

    try:
        account = client.get_account()
        return _build_status_df(
            "get_account_df",
            account_id=_stringify(getattr(account, "id", "")),
            account_number=_stringify(getattr(account, "account_number", "")),
            status=_stringify(getattr(account, "status", "")),
            currency=_stringify(getattr(account, "currency", "")),
            cash=_stringify(getattr(account, "cash", "")),
            buying_power=_stringify(getattr(account, "buying_power", "")),
            equity=_stringify(getattr(account, "equity", "")),
            portfolio_value=_stringify(getattr(account, "portfolio_value", "")),
            long_market_value=_stringify(getattr(account, "long_market_value", "")),
            short_market_value=_stringify(getattr(account, "short_market_value", "")),
        )
    except Exception as exc:  # pragma: no cover - network/auth path
        return _build_error_df(
            function_name="get_account_df",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def get_connection_status_df(trading_client: Any = _AUTO) -> pd.DataFrame:
    if trading_client is None:
        return _build_error_df(
            function_name="get_connection_status_df",
            error_type="MissingClient",
            error_message="TradingClient is required",
        )

    account_df = get_account_df(trading_client=trading_client)
    if not bool(account_df.loc[0, "ok"]):
        account_df.loc[0, "function_name"] = "get_connection_status_df"
        return account_df

    row = account_df.iloc[0].to_dict()
    row["function_name"] = "get_connection_status_df"
    return pd.DataFrame([row])


def get_price_data_df(
    symbol: str,
    lookback_days: int = 60,
    timeframe: str = "1Day",
    data_client: Any = _AUTO,
    crypto_data_client: Any = _AUTO,
) -> pd.DataFrame:
    normalized_symbol = _normalize_symbol(symbol)
    canonical_crypto_symbol = _canonicalize_crypto_symbol(symbol)

    if canonical_crypto_symbol is not None and (
        "/" in normalized_symbol
        or "-" in normalized_symbol
        or normalized_symbol == canonical_crypto_symbol.replace("/", "")
    ):
        normalized = _fetch_crypto_price_data_df(
            symbol=canonical_crypto_symbol or normalized_symbol,
            lookback_days=lookback_days,
            timeframe=timeframe,
            crypto_data_client=crypto_data_client,
        )
    else:
        normalized = _fetch_stock_price_data_df(
            symbol=normalized_symbol,
            lookback_days=lookback_days,
            timeframe=timeframe,
            data_client=data_client,
        )
        if normalized.empty and canonical_crypto_symbol is not None:
            normalized = _fetch_crypto_price_data_df(
                symbol=canonical_crypto_symbol,
                lookback_days=lookback_days,
                timeframe=timeframe,
                crypto_data_client=crypto_data_client,
            )

    if "ok" in normalized.columns and not normalized.empty:
        return normalized
    if normalized.empty:
        target_symbol = canonical_crypto_symbol or normalized_symbol
        return _build_error_df(
            function_name="get_price_data_df",
            error_type="NoPriceData",
            error_message=f"No price data returned for {target_symbol}",
        )
    return normalized


def get_positions_df(trading_client: Any = _AUTO) -> pd.DataFrame:
    client, error_df = _resolve_trading_client(trading_client, "get_positions_df")
    if error_df is not None:
        return error_df

    try:
        positions = client.get_all_positions()
        rows = []
        for position in positions:
            rows.append(
                {
                    "symbol": _stringify(getattr(position, "symbol", "")),
                    "qty": _stringify(getattr(position, "qty", "")),
                    "side": _stringify(getattr(position, "side", "")),
                    "market_value": _stringify(getattr(position, "market_value", "")),
                    "avg_entry_price": _stringify(getattr(position, "avg_entry_price", "")),
                    "current_price": _stringify(getattr(position, "current_price", "")),
                    "unrealized_pl": _stringify(getattr(position, "unrealized_pl", "")),
                }
            )
        if not rows:
            return _empty_df(POSITION_COLUMNS)
        return pd.DataFrame(rows)[POSITION_COLUMNS]
    except Exception as exc:  # pragma: no cover - network/auth path
        return _build_error_df(
            function_name="get_positions_df",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def get_open_orders_df(symbol: str | None = None, trading_client: Any = _AUTO) -> pd.DataFrame:
    client, error_df = _resolve_trading_client(trading_client, "get_open_orders_df")
    if error_df is not None:
        return error_df

    try:
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        orders = client.get_orders(filter=request)
        rows = [_extract_order_row(order) for order in orders]
        df = _empty_df(ORDER_COLUMNS) if not rows else pd.DataFrame(rows)[ORDER_COLUMNS]
        if symbol and not df.empty:
            df = df[df["symbol"].apply(lambda value: _symbols_match(symbol, value))].reset_index(drop=True)
        return df
    except Exception as exc:  # pragma: no cover - network/auth path
        return _build_error_df(
            function_name="get_open_orders_df",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def _get_current_position_qty(symbol: str, trading_client: Any = _AUTO) -> tuple[int, pd.DataFrame | None]:
    positions_df = get_positions_df(trading_client=trading_client)
    if "ok" in positions_df.columns and not positions_df.empty and not bool(positions_df.loc[0, "ok"]):
        return 0, positions_df
    if positions_df.empty:
        return 0, None

    match = positions_df[positions_df["symbol"].apply(lambda value: _symbols_match(symbol, value))]
    if match.empty:
        return 0, None
    return _safe_int(match.iloc[0]["qty"]), None


def generate_spy_sma_signal_df(
    symbol: str = "SPY",
    qty: int = 1,
    timeframe: str = "1Day",
    lookback_days: int = 60,
    price_df: pd.DataFrame | None = None,
    trading_client: Any = _AUTO,
    data_client: Any = _AUTO,
    crypto_data_client: Any = _AUTO,
) -> pd.DataFrame:
    if price_df is None:
        price_df = get_price_data_df(
            symbol=symbol,
            lookback_days=lookback_days,
            timeframe=timeframe,
            data_client=data_client,
            crypto_data_client=crypto_data_client,
        )
    if "ok" in price_df.columns and not price_df.empty and not bool(price_df.loc[0, "ok"]):
        return price_df
    if price_df.empty:
        return _build_error_df(
            function_name="generate_spy_sma_signal_df",
            error_type="NoPriceData",
            error_message=f"No price data available for {symbol}",
        )

    latest = price_df.sort_values("timestamp").iloc[-1]
    current_qty, positions_error = _get_current_position_qty(symbol, trading_client=trading_client)
    if positions_error is not None:
        return positions_error

    return evaluate_sma_signal_row(
        symbol=symbol,
        qty=qty,
        latest_close=_safe_float(latest["close"]),
        latest_sma20=_safe_float(latest["sma20"]),
        has_position=current_qty > 0,
    )


def submit_market_order_df(
    symbol: str,
    qty: int,
    side: str,
    time_in_force: str = "day",
    trading_client: Any = _AUTO,
) -> pd.DataFrame:
    client, error_df = _resolve_trading_client(trading_client, "submit_market_order_df")
    if error_df is not None:
        return error_df

    normalized_symbol = _canonicalize_crypto_symbol(symbol) or _normalize_symbol(symbol)
    is_crypto = _is_crypto_symbol(symbol)
    side_lookup = {
        "buy": OrderSide.BUY,
        "sell": OrderSide.SELL,
    }
    tif_lookup = {
        "day": TimeInForce.DAY,
        "gtc": TimeInForce.GTC,
        "ioc": TimeInForce.IOC,
    }
    normalized_time_in_force = time_in_force.lower()
    if is_crypto and normalized_time_in_force == "day":
        normalized_time_in_force = "gtc"
    try:
        order_request = MarketOrderRequest(
            symbol=normalized_symbol,
            qty=qty,
            side=side_lookup[side.lower()],
            time_in_force=tif_lookup[normalized_time_in_force],
        )
        order = client.submit_order(order_data=order_request)
        df = normalize_order_response_df(order, paper=True)
        df.loc[0, "function_name"] = "submit_market_order_df"
        append_trade_log_row(
            {
                "timestamp_utc": _utc_now_iso(),
                "event_type": "submit_market_order",
                "symbol": normalized_symbol,
                "qty": qty,
                "side": side.lower(),
                "ok": True,
                "order_id": df.loc[0, "order_id"],
                "status": df.loc[0, "status"],
            }
        )
        return df
    except Exception as exc:  # pragma: no cover - network/auth path
        error = _build_error_df(
            function_name="submit_market_order_df",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        append_trade_log_row(
            {
                "timestamp_utc": _utc_now_iso(),
                "event_type": "submit_market_order",
                "symbol": normalized_symbol,
                "qty": qty,
                "side": side.lower(),
                "ok": False,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )
        return error


def cancel_open_orders_df(symbol: str | None = None, trading_client: Any = _AUTO) -> pd.DataFrame:
    client, error_df = _resolve_trading_client(trading_client, "cancel_open_orders_df")
    if error_df is not None:
        return error_df

    orders_df = get_open_orders_df(symbol=symbol, trading_client=client)
    if "ok" in orders_df.columns and not orders_df.empty and not bool(orders_df.loc[0, "ok"]):
        return orders_df
    if orders_df.empty:
        return _empty_df(CANCEL_COLUMNS)

    rows = []
    for _, order_row in orders_df.iterrows():
        order_id = order_row["order_id"]
        try:
            client.cancel_order_by_id(order_id)
            row = {
                "ok": True,
                "paper": True,
                "function_name": "cancel_open_orders_df",
                "timestamp_utc": _utc_now_iso(),
                "error_type": "",
                "error_message": "",
                "order_id": order_id,
                "symbol": order_row.get("symbol", ""),
                "cancel_requested": True,
            }
        except Exception as exc:  # pragma: no cover - network/auth path
            row = {
                "ok": False,
                "paper": True,
                "function_name": "cancel_open_orders_df",
                "timestamp_utc": _utc_now_iso(),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "order_id": order_id,
                "symbol": order_row.get("symbol", ""),
                "cancel_requested": False,
            }
        rows.append(row)
        append_trade_log_row(
            {
                "timestamp_utc": row["timestamp_utc"],
                "event_type": "cancel_open_order",
                "symbol": row["symbol"],
                "ok": row["ok"],
                "order_id": row["order_id"],
                "error_type": row["error_type"],
                "error_message": row["error_message"],
            }
        )
    return pd.DataFrame(rows)[CANCEL_COLUMNS]


def run_spy_sma_paper_bot_df(
    symbol: str = "SPY",
    qty: int = 1,
    timeframe: str = "1Day",
    lookback_days: int = 60,
    max_position_qty: int = 1,
    submit_orders: bool = False,
    price_df: pd.DataFrame | None = None,
    account_df: pd.DataFrame | None = None,
    has_position: bool | None = None,
    trading_client: Any = _AUTO,
    data_client: Any = _AUTO,
    crypto_data_client: Any = _AUTO,
) -> pd.DataFrame:
    function_name = "run_spy_sma_paper_bot_df"

    if account_df is None:
        account_df = get_account_df(trading_client=trading_client)
    if "ok" in account_df.columns and not account_df.empty and not bool(account_df.loc[0, "ok"]):
        return account_df

    if price_df is None:
        price_df = get_price_data_df(
            symbol=symbol,
            lookback_days=lookback_days,
            timeframe=timeframe,
            data_client=data_client,
            crypto_data_client=crypto_data_client,
        )
    if "ok" in price_df.columns and not price_df.empty and not bool(price_df.loc[0, "ok"]):
        return price_df
    if price_df.empty:
        return _build_error_df(
            function_name=function_name,
            error_type="MissingPriceData",
            error_message="Price data is required",
        )

    latest = price_df.sort_values("timestamp").iloc[-1]
    latest_close = _safe_float(latest["close"])
    latest_sma20 = _safe_float(latest["sma20"], default=float("nan"))
    if pd.isna(latest_sma20):
        result = _build_status_df(
            function_name,
            symbol=symbol,
            qty=qty,
            close=latest_close,
            sma20=latest_sma20,
            signal="DO_NOTHING",
            action="NOT_ENOUGH_DATA",
            order_submitted=False,
            order_id="",
            has_position=False if has_position is None else has_position,
            max_position_qty=max_position_qty,
        )
        append_trade_log_row(result.iloc[0].to_dict())
        return result

    current_qty = 0
    if has_position is None:
        current_qty, positions_error = _get_current_position_qty(symbol, trading_client=trading_client)
        if positions_error is not None:
            return positions_error
        position_flag = current_qty > 0
    else:
        position_flag = bool(has_position)
        current_qty = qty if position_flag else 0

    signal_df = evaluate_sma_signal_row(
        symbol=symbol,
        qty=qty,
        latest_close=latest_close,
        latest_sma20=latest_sma20,
        has_position=position_flag,
    )

    risk_df = enforce_max_position_size(
        symbol=symbol,
        current_qty=current_qty,
        requested_qty=qty,
        max_position_qty=max_position_qty,
    )

    signal = signal_df.loc[0, "signal"]
    should_submit = bool(signal_df.loc[0, "should_submit_order"])
    action = "DO_NOTHING"
    order_submitted = False
    order_id = ""

    if should_submit and not bool(risk_df.loc[0, "ok"]):
        action = "BLOCKED_BY_RISK"
    elif should_submit and not submit_orders:
        action = "DRY_RUN_BUY"
    elif should_submit and submit_orders:
        order_df = submit_market_order_df(
            symbol=symbol,
            qty=qty,
            side="buy",
            trading_client=trading_client,
        )
        if bool(order_df.loc[0, "ok"]):
            action = "BUY_SUBMITTED"
            order_submitted = True
            order_id = order_df.loc[0, "order_id"]
        else:
            action = "BUY_FAILED"
    elif signal == "BUY" and position_flag:
        action = "ALREADY_HOLDING"

    result = _build_status_df(
        function_name,
        symbol=symbol,
        qty=qty,
        close=latest_close,
        sma20=latest_sma20,
        signal=signal,
        action=action,
        order_submitted=order_submitted,
        order_id=order_id,
        has_position=position_flag,
        max_position_qty=max_position_qty,
    )
    append_trade_log_row(result.iloc[0].to_dict())
    return result
