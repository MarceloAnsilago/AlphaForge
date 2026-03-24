from __future__ import annotations

from typing import Any


def build_source_options(indicators: list[str], price_fields: list[str]) -> list[str]:
    price_options = [f"PRICE:{field}" for field in price_fields]
    indicator_options = [f"INDICATOR:{indicator}" for indicator in indicators]
    return price_options + indicator_options


def parse_source_option(option: str) -> dict[str, Any]:
    source_kind, source_name = option.split(":", maxsplit=1)
    return {
        "kind": source_kind.lower(),
        "name": source_name,
    }


def format_source_option(option: str) -> str:
    parsed = parse_source_option(option)
    if parsed["kind"] == "price":
        return f"Preço: {parsed['name']}"
    return f"Indicador: {parsed['name']}"


def build_operand(
    operand_type: str,
    value: str | float,
    period: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": operand_type,
        "value": value,
    }
    if period is not None:
        payload["period"] = period
    return payload


def humanize_rule_name(prefix: str) -> str:
    tokens = prefix.replace("_", " ").split()
    return " ".join(token.capitalize() for token in tokens)
