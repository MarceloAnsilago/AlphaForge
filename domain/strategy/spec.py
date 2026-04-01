from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


STRATEGY_SPEC_VERSION = "strategy-spec/1"
STRATEGY_DRAFT_VERSION = "strategy-draft/1"

VALID_DIRECTIONS = {"BUY", "SELL", "BOTH", "NONE"}
VALID_SOURCE_TYPES = {"price", "indicator", "fixed", "special"}
VALID_CONNECTORS = {"SE", "E", "E SE", "E Tambem", "OU", "OU SE", "OU Tambem"}
VALID_OPERATORS = {
    "GREATER_THAN",
    "LESS_THAN",
    "GREATER_OR_EQUAL",
    "LESS_OR_EQUAL",
    "EQUAL",
    "NOT_EQUAL",
    "CROSS_UP",
    "CROSS_DOWN",
    "CROSS_AND_CLOSE_ABOVE",
    "CROSS_AND_CLOSE_BELOW",
}
VALID_PRICE_FIELDS = {"open", "high", "low", "close"}
VALID_SPECIAL_SOURCES = {
    "CANDLE_SIZE",
    "CANDLE_BODY",
    "DAY_OPEN",
    "DAY_HIGH",
    "DAY_LOW",
    "DAY_CLOSE",
}


@dataclass(slots=True)
class StrategyDraft:
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "StrategyDraft":
        return cls(payload=dict(payload))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@dataclass(slots=True)
class StrategySourceSpec:
    source_type: str
    value: str | float
    label: str | None = None
    candle_offset: int = 0
    indicator_name: str | None = None
    indicator_output: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    slot_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StrategyRuleSpec:
    source_a: StrategySourceSpec
    operator: str
    source_b: StrategySourceSpec
    connector: str = "SE"
    group_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_a": self.source_a.to_dict(),
            "operator": self.operator,
            "source_b": self.source_b.to_dict(),
            "connector": self.connector,
            "group_id": self.group_id,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class StrategyRiskTargetSpec:
    type: str = "NONE"
    value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StrategyRiskManagementSpec:
    stop: StrategyRiskTargetSpec = field(default_factory=StrategyRiskTargetSpec)
    take: StrategyRiskTargetSpec = field(default_factory=StrategyRiskTargetSpec)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop": self.stop.to_dict(),
            "take": self.take.to_dict(),
        }


@dataclass(slots=True)
class StrategySpec:
    version: str
    name: str
    direction: str
    settings: dict[str, Any]
    market: dict[str, Any]
    entry_rules: list[StrategyRuleSpec] = field(default_factory=list)
    exit_rules: list[StrategyRuleSpec] = field(default_factory=list)
    risk_management: StrategyRiskManagementSpec = field(default_factory=StrategyRiskManagementSpec)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "direction": self.direction,
            "settings": dict(self.settings),
            "market": dict(self.market),
            "entry_rules": [rule.to_dict() for rule in self.entry_rules],
            "exit_rules": [rule.to_dict() for rule in self.exit_rules],
            "risk_management": self.risk_management.to_dict(),
        }
