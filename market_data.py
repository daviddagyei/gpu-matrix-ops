from __future__ import annotations

from typing import Callable

import pandas as pd


MARKET_DATA_PROVIDERS: dict[str, Callable[[dict], pd.DataFrame]] = {}


def register_market_data_provider(name: str):
    def decorator(func):
        MARKET_DATA_PROVIDERS[name] = func
        return func

    return decorator


@register_market_data_provider("alpaca")
def alpaca_market_data_provider(config: dict) -> pd.DataFrame:
    from alpaca_engine import get_price_data_df

    return get_price_data_df(
        symbol=config["symbol"],
        lookback_days=int(config.get("lookback_days", 60)),
        timeframe=config.get("timeframe", "1Day"),
    )
