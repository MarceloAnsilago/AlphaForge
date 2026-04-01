from __future__ import annotations

from collections import defaultdict
from typing import Any

from domain.strategy.spec import (
    STRATEGY_SPEC_VERSION,
    StrategyRuleSpec,
    StrategySourceSpec,
    StrategySpec,
    VALID_CONNECTORS,
    VALID_DIRECTIONS,
    VALID_OPERATORS,
    VALID_PRICE_FIELDS,
    VALID_SOURCE_TYPES,
    VALID_SPECIAL_SOURCES,
)


class StrategyValidationError(ValueError):
    pass


def _raise(path: str, message: str) -> None:
    raise StrategyValidationError(f"{path}: {message}")


def _validate_source(source: StrategySourceSpec, path: str) -> None:
    if source.source_type not in VALID_SOURCE_TYPES:
        _raise(path, f"source_type invalido: {source.source_type}")

    if not isinstance(source.candle_offset, int):
        _raise(path, "candle_offset deve ser inteiro")

    if source.source_type == "price" and str(source.value) not in VALID_PRICE_FIELDS:
        _raise(path, f"price invalido: {source.value}")

    if source.source_type == "special" and str(source.value) not in VALID_SPECIAL_SOURCES:
        _raise(path, f"special source invalido: {source.value}")

    if source.source_type == "fixed":
        try:
            float(source.value)
        except (TypeError, ValueError):
            _raise(path, f"fixed invalido: {source.value}")

    if source.source_type == "indicator":
        indicator_name = source.indicator_name or str(source.value or "")
        if not indicator_name:
            _raise(path, "indicator sem nome")
        if source.indicator_output is not None and not str(source.indicator_output).strip():
            _raise(path, "indicator_output vazio")


def _validate_rule(rule: StrategyRuleSpec, path: str) -> None:
    if rule.operator not in VALID_OPERATORS:
        _raise(path, f"operator invalido: {rule.operator}")
    if rule.connector not in VALID_CONNECTORS:
        _raise(path, f"connector invalido: {rule.connector}")
    if not str(rule.group_id).strip():
        _raise(path, "group_id vazio")

    metadata_side = rule.metadata.get("side")
    if metadata_side is not None and str(metadata_side).upper() not in {"BUY", "SELL"}:
        _raise(path, f"metadata.side invalido: {metadata_side}")

    _validate_source(rule.source_a, f"{path}.source_a")
    _validate_source(rule.source_b, f"{path}.source_b")


def _validate_group_sides(rules: list[StrategyRuleSpec], path: str) -> None:
    grouped_sides: dict[str, set[str]] = defaultdict(set)
    for rule in rules:
        side = rule.metadata.get("side")
        if side is not None:
            grouped_sides[rule.group_id].add(str(side).upper())

    for group_id, sides in grouped_sides.items():
        if len(sides) > 1:
            _raise(path, f"group_id {group_id} possui lados conflitantes: {sorted(sides)}")


def validate_strategy_spec(spec: StrategySpec) -> StrategySpec:
    if spec.version != STRATEGY_SPEC_VERSION:
        _raise("version", f"versao de spec nao suportada: {spec.version}")

    if spec.direction not in VALID_DIRECTIONS:
        _raise("direction", f"direcao invalida: {spec.direction}")

    if not spec.name.strip():
        _raise("name", "nome vazio")

    if not isinstance(spec.settings, dict):
        _raise("settings", "settings deve ser dict")
    if not isinstance(spec.market, dict):
        _raise("market", "market deve ser dict")

    for index, rule in enumerate(spec.entry_rules):
        _validate_rule(rule, f"entry_rules[{index}]")
    for index, rule in enumerate(spec.exit_rules):
        _validate_rule(rule, f"exit_rules[{index}]")

    _validate_group_sides(spec.entry_rules, "entry_rules")
    _validate_group_sides(spec.exit_rules, "exit_rules")

    return spec
