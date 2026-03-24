from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Operand:
    type: str
    value: str | float
    period: int | None = None


@dataclass(slots=True)
class Rule:
    left: Operand
    operator: str
    right: Operand
    candle_offset: int


@dataclass(slots=True)
class RiskTarget:
    type: str
    value: float


@dataclass(slots=True)
class RiskManagement:
    stop: RiskTarget
    take: RiskTarget


@dataclass(slots=True)
class StrategyStructure:
    name: str
    direction: str
    settings: dict[str, Any]
    market: dict[str, Any]
    entry_rules: list[Rule]
    exit_rules: list[Rule]
    risk_management: RiskManagement

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_operand(payload: dict[str, Any]) -> Operand:
    return Operand(
        type=payload["type"],
        value=payload["value"],
        period=payload.get("period"),
    )


def _build_rule(payload: dict[str, Any]) -> Rule:
    return Rule(
        left=_build_operand(payload["left"]),
        operator=payload["operator"],
        right=_build_operand(payload["right"]),
        candle_offset=payload["candle_offset"],
    )


def build_strategy_structure(
    name: str,
    direction: str,
    settings: dict[str, Any],
    market: dict[str, Any],
    entry_rules: list[dict[str, Any]],
    exit_rules: list[dict[str, Any]],
    risk_management: dict[str, Any],
) -> dict[str, Any]:
    strategy = StrategyStructure(
        name=name,
        direction=direction,
        settings=settings,
        market=market,
        entry_rules=[_build_rule(rule) for rule in entry_rules],
        exit_rules=[_build_rule(rule) for rule in exit_rules],
        risk_management=RiskManagement(
            stop=RiskTarget(**risk_management["stop"]),
            take=RiskTarget(**risk_management["take"]),
        ),
    )
    return strategy.to_dict()
