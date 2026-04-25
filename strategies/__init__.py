from __future__ import annotations

STRATEGY_REGISTRY = {}


def register_strategy(name: str):
    def decorator(func):
        STRATEGY_REGISTRY[name] = func
        return func

    return decorator


from . import rsi_mean_reversion_scalp  # noqa: E402,F401
from . import sma_trend  # noqa: E402,F401
