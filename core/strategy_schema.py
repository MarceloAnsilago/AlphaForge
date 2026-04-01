from __future__ import annotations

from typing import Any

from domain.strategy.normalizer import build_strategy_draft


def build_strategy_structure(
    name: str,
    direction: str,
    settings: dict[str, Any],
    market: dict[str, Any],
    entry_rules: list[dict[str, Any]],
    exit_rules: list[dict[str, Any]],
    risk_management: dict[str, Any],
) -> dict[str, Any]:
    draft = build_strategy_draft(
        name=name,
        direction=direction,
        settings=settings,
        market=market,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        risk_management=risk_management,
    )
    return draft.to_dict()
