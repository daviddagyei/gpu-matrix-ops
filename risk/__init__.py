from __future__ import annotations

RISK_RULE_REGISTRY = {}


def register_risk_rule(name: str):
    def decorator(func):
        RISK_RULE_REGISTRY[name] = func
        return func

    return decorator


from . import basic_rules  # noqa: E402,F401
