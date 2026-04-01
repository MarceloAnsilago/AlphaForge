from __future__ import annotations

from copy import deepcopy
from typing import Any

from domain.strategy.spec import (
    STRATEGY_DRAFT_VERSION,
    STRATEGY_SPEC_VERSION,
    StrategyDraft,
    StrategyRiskManagementSpec,
    StrategyRiskTargetSpec,
    StrategyRuleSpec,
    StrategySourceSpec,
    StrategySpec,
)
from domain.strategy.validator import validate_strategy_spec


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_version(payload: dict[str, Any]) -> str:
    raw_version = str(payload.get("version") or "").strip()
    if raw_version in {STRATEGY_SPEC_VERSION, STRATEGY_DRAFT_VERSION}:
        return raw_version
    return STRATEGY_DRAFT_VERSION


def _normalize_source(payload: dict[str, Any]) -> StrategySourceSpec:
    return StrategySourceSpec(
        source_type=str(payload.get("source_type", "")).lower(),
        value=payload.get("value", ""),
        label=payload.get("label"),
        candle_offset=_as_int(payload.get("candle_offset", 0)),
        indicator_name=payload.get("indicator_name"),
        indicator_output=payload.get("indicator_output") or ("Valor" if payload.get("source_type") == "indicator" else None),
        parameters=deepcopy(payload.get("parameters", {})),
        slot_number=payload.get("slot_number"),
    )


def _normalize_legacy_rule(payload: dict[str, Any]) -> dict[str, Any]:
    if "left" not in payload or "right" not in payload:
        return payload

    left_source = {
        "source_type": payload["left"]["type"],
        "value": payload["left"]["value"],
        "candle_offset": _as_int(payload.get("candle_offset", 0)),
        "parameters": {"period": payload["left"].get("period")},
    }
    right_source = {
        "source_type": payload["right"]["type"],
        "value": payload["right"]["value"],
        "candle_offset": _as_int(payload.get("candle_offset", 0)),
        "parameters": {"period": payload["right"].get("period")},
    }
    return {
        "source_a": left_source,
        "operator": payload["operator"],
        "source_b": right_source,
        "connector": "SE",
        "group_id": "legacy",
        "metadata": {"legacy_rule": True},
    }


def _normalize_rule(payload: dict[str, Any], position: int) -> StrategyRuleSpec:
    normalized = _normalize_legacy_rule(payload)
    metadata = deepcopy(normalized.get("metadata", {}))
    if metadata.get("side") is not None:
        metadata["side"] = str(metadata["side"]).upper()

    connector = str(normalized.get("connector", "SE"))
    if position == 0:
        connector = "SE"

    return StrategyRuleSpec(
        source_a=_normalize_source(normalized["source_a"]),
        operator=str(normalized["operator"]).upper(),
        source_b=_normalize_source(normalized["source_b"]),
        connector=connector,
        group_id=str(normalized.get("group_id", f"group_{position}")),
        metadata=metadata,
    )


def _normalize_rules(rules: list[dict[str, Any]]) -> list[StrategyRuleSpec]:
    return [_normalize_rule(rule, index) for index, rule in enumerate(rules)]


def _normalize_risk_target(payload: dict[str, Any] | None) -> StrategyRiskTargetSpec:
    payload = payload or {}
    return StrategyRiskTargetSpec(
        type=str(payload.get("type", "NONE")),
        value=_as_float(payload.get("value", 0.0)),
    )


def _normalize_risk_management(payload: dict[str, Any] | None) -> StrategyRiskManagementSpec:
    payload = payload or {}
    return StrategyRiskManagementSpec(
        stop=_normalize_risk_target(payload.get("stop")),
        take=_normalize_risk_target(payload.get("take")),
    )


def normalize_strategy(strategy: StrategySpec | StrategyDraft | dict[str, Any]) -> StrategySpec:
    if isinstance(strategy, StrategySpec):
        return validate_strategy_spec(strategy)

    if isinstance(strategy, StrategyDraft):
        payload = strategy.to_dict()
    else:
        payload = dict(strategy)

    version = _normalize_version(payload)
    if version == STRATEGY_SPEC_VERSION:
        spec = StrategySpec(
            version=STRATEGY_SPEC_VERSION,
            name=str(payload.get("name") or "Unnamed Strategy"),
            direction=str(payload.get("direction", "NONE")).upper(),
            settings=deepcopy(payload.get("settings", {})),
            market=deepcopy(payload.get("market", {})),
            entry_rules=_normalize_rules(payload.get("entry_rules", [])),
            exit_rules=_normalize_rules(payload.get("exit_rules", [])),
            risk_management=_normalize_risk_management(payload.get("risk_management")),
        )
        return validate_strategy_spec(spec)

    spec = StrategySpec(
        version=STRATEGY_SPEC_VERSION,
        name=str(payload.get("name") or "Unnamed Strategy"),
        direction=str(payload.get("direction", "NONE")).upper(),
        settings=deepcopy(payload.get("settings", {})),
        market=deepcopy(payload.get("market", {})),
        entry_rules=_normalize_rules(payload.get("entry_rules", [])),
        exit_rules=_normalize_rules(payload.get("exit_rules", [])),
        risk_management=_normalize_risk_management(payload.get("risk_management")),
    )
    return validate_strategy_spec(spec)


def build_strategy_draft(
    name: str,
    direction: str,
    settings: dict[str, Any],
    market: dict[str, Any],
    entry_rules: list[dict[str, Any]],
    exit_rules: list[dict[str, Any]],
    risk_management: dict[str, Any],
) -> StrategyDraft:
    payload = {
        "version": STRATEGY_DRAFT_VERSION,
        "name": name,
        "direction": direction,
        "settings": deepcopy(settings),
        "market": deepcopy(market),
        "entry_rules": deepcopy(entry_rules),
        "exit_rules": deepcopy(exit_rules),
        "risk_management": deepcopy(risk_management),
    }
    return StrategyDraft.from_payload(payload)
