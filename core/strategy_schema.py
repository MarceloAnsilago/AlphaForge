from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class RuleSource:
    source_type: str
    value: str | float
    label: str | None = None
    candle_offset: int = 0
    indicator_name: str | None = None
    indicator_output: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    slot_number: int | None = None


@dataclass(slots=True)
class Rule:
    source_a: RuleSource
    operator: str
    source_b: RuleSource
    source_b_type: str
    candle_offset: int
    connector: str = "SE"
    group_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)


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


def _build_rule_source(payload: dict[str, Any]) -> RuleSource:
    return RuleSource(
        source_type=payload["source_type"],
        value=payload["value"],
        label=payload.get("label"),
        candle_offset=int(payload.get("candle_offset", 0)),
        indicator_name=payload.get("indicator_name"),
        indicator_output=payload.get("indicator_output"),
        parameters=payload.get("parameters", {}),
        slot_number=payload.get("slot_number"),
    )


def _build_rule(payload: dict[str, Any]) -> Rule:
    if "left" in payload and "right" in payload:
        left_source = {
            "source_type": payload["left"]["type"],
            "value": payload["left"]["value"],
            "candle_offset": int(payload.get("candle_offset", 0)),
            "parameters": {"period": payload["left"].get("period")},
        }
        right_source = {
            "source_type": payload["right"]["type"],
            "value": payload["right"]["value"],
            "candle_offset": int(payload.get("candle_offset", 0)),
            "parameters": {"period": payload["right"].get("period")},
        }
        payload = {
            "source_a": left_source,
            "operator": payload["operator"],
            "source_b": right_source,
            "source_b_type": right_source["source_type"],
            "candle_offset": int(payload["candle_offset"]),
            "connector": "SE",
            "group_id": "legacy",
            "metadata": {"legacy_rule": True},
        }

    return Rule(
        source_a=_build_rule_source(payload["source_a"]),
        operator=payload["operator"],
        source_b=_build_rule_source(payload["source_b"]),
        source_b_type=payload.get("source_b_type", payload["source_b"]["source_type"]),
        candle_offset=int(payload.get("candle_offset", payload["source_a"].get("candle_offset", 0))),
        connector=payload.get("connector", "SE"),
        group_id=payload.get("group_id", "default"),
        metadata=payload.get("metadata", {}),
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
