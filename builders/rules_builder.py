from __future__ import annotations

from copy import deepcopy
from typing import Any


CONNECTOR_START = "SE"
DEFAULT_GROUP_ID = "manual_signal_rules"

AND_CONNECTORS = {"SE", "E", "E SE", "E Tambem"}
OR_CONNECTORS = {"OU", "OU SE", "OU Tambem"}

SPECIAL_SOURCE_TO_PRICE = {
    "CURRENT_PRICE": "close",
    "CANDLE_CLOSE": "close",
    "CANDLE_OPEN": "open",
    "CANDLE_HIGH": "high",
    "CANDLE_LOW": "low",
}

OPPOSITE_OPERATOR_MAP = {
    "GREATER_THAN": "LESS_THAN",
    "LESS_THAN": "GREATER_THAN",
    "GREATER_OR_EQUAL": "LESS_OR_EQUAL",
    "LESS_OR_EQUAL": "GREATER_OR_EQUAL",
    "EQUAL": "NOT_EQUAL",
    "NOT_EQUAL": "EQUAL",
    "CROSS_UP": "CROSS_DOWN",
    "CROSS_DOWN": "CROSS_UP",
    "CROSS_AND_CLOSE_ABOVE": "CROSS_AND_CLOSE_BELOW",
    "CROSS_AND_CLOSE_BELOW": "CROSS_AND_CLOSE_ABOVE",
}


def _make_price_source(
    value: str,
    label: str,
    candle_offset: int = 0,
) -> dict[str, Any]:
    return {
        "source_type": "price",
        "value": value,
        "label": label,
        "candle_offset": int(candle_offset),
    }


def _make_fixed_source(
    value: float,
    label: str,
    candle_offset: int = 0,
) -> dict[str, Any]:
    return {
        "source_type": "fixed",
        "value": float(value),
        "label": label,
        "candle_offset": int(candle_offset),
    }


def _make_indicator_source(
    indicator_name: str,
    output_name: str,
    parameters: dict[str, Any],
    label: str,
    candle_offset: int = 0,
    slot_number: int | None = None,
) -> dict[str, Any]:
    return {
        "source_type": "indicator",
        "value": indicator_name,
        "label": label,
        "candle_offset": int(candle_offset),
        "indicator_name": indicator_name,
        "indicator_output": output_name,
        "parameters": parameters,
        "slot_number": slot_number,
    }


def _make_special_source(
    value: str,
    label: str,
    candle_offset: int = 0,
) -> dict[str, Any]:
    return {
        "source_type": "special",
        "value": value,
        "label": label,
        "candle_offset": int(candle_offset),
    }


def _make_rule(
    source_a: dict[str, Any],
    operator: str,
    source_b: dict[str, Any],
    connector: str,
    group_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source_a": source_a,
        "operator": operator,
        "source_b": source_b,
        "source_b_type": source_b["source_type"],
        "candle_offset": int(source_a.get("candle_offset", 0)),
        "connector": connector,
        "group_id": group_id,
        "metadata": metadata or {},
    }


def _source_from_ui(
    source_payload: dict[str, Any],
    candle_payload: dict[str, Any],
    signal_settings: dict[str, Any],
) -> dict[str, Any] | None:
    raw_value = source_payload["value"]
    label = source_payload["label"]
    candle_offset = int(candle_payload["value"])

    if raw_value in {"NONE", "EMPTY_VALUE"}:
        return None

    if raw_value.startswith("PRICE:"):
        return _make_price_source(
            raw_value.split(":", maxsplit=1)[1],
            label,
            candle_offset,
        )

    if raw_value.startswith("INDICATOR_"):
        indicator_token, output_name = raw_value.split(":", maxsplit=1)
        slot_number = int(indicator_token.split("_")[1])
        indicator_name = signal_settings.get(f"indicator_{slot_number}", "Nao usar")
        indicator_parameters = deepcopy(signal_settings.get(f"indicator_{slot_number}_parameters", {}))
        return _make_indicator_source(
            indicator_name=indicator_name,
            output_name=output_name,
            parameters=indicator_parameters,
            label=label,
            candle_offset=candle_offset,
            slot_number=slot_number,
        )

    mapped_price = SPECIAL_SOURCE_TO_PRICE.get(raw_value)
    if mapped_price is not None:
        return _make_price_source(mapped_price, label, candle_offset)

    return _make_special_source(raw_value, label, candle_offset)


def _normalize_connectors(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rules:
        return []

    normalized_rules = []
    for index, rule in enumerate(rules):
        normalized_rule = deepcopy(rule)
        if index == 0:
            normalized_rule["connector"] = CONNECTOR_START
        normalized_rules.append(normalized_rule)
    return normalized_rules


def _invert_rule(rule: dict[str, Any], scope: str) -> dict[str, Any]:
    inverted_rule = deepcopy(rule)
    inverted_rule["operator"] = OPPOSITE_OPERATOR_MAP.get(rule["operator"], rule["operator"])
    inverted_rule["metadata"] = {
        **rule.get("metadata", {}),
        "scope": scope,
        "generated_from": "entry_inverse",
    }
    return inverted_rule


def _build_manual_rules(
    ready_signals: dict[str, Any],
    scope: str,
) -> list[dict[str, Any]]:
    signal_settings = ready_signals.get("signal_settings", {})
    ui_rules = signal_settings.get("rules", [])
    built_rules: list[dict[str, Any]] = []

    for index, ui_rule in enumerate(ui_rules):
        source_a = _source_from_ui(ui_rule["source_a"], ui_rule["candle_a"], signal_settings)
        source_b = _source_from_ui(ui_rule["source_b"], ui_rule["candle_b"], signal_settings)
        if source_a is None or source_b is None:
            continue

        built_rules.append(
            _make_rule(
                source_a=source_a,
                operator=ui_rule["operator"]["value"],
                source_b=source_b,
                connector=ui_rule["logical_command"],
                group_id=DEFAULT_GROUP_ID,
                metadata={
                    "scope": scope,
                    "source": "signal_settings",
                    "order": index,
                },
            )
        )

    return _normalize_connectors(built_rules)


def _build_crossover_group(
    operator: str,
    connector: str,
    group_id: str,
    signal_config: dict[str, Any],
    side: str,
    scope: str,
) -> dict[str, Any]:
    fast_source = _make_indicator_source(
        indicator_name=signal_config["fast_indicator"],
        output_name="Valor",
        parameters={"period": int(signal_config["fast_period"])},
        label=f"{signal_config['fast_indicator']} rapido",
    )
    slow_source = _make_indicator_source(
        indicator_name=signal_config["slow_indicator"],
        output_name="Valor",
        parameters={"period": int(signal_config["slow_period"])},
        label=f"{signal_config['slow_indicator']} lento",
    )
    return _make_rule(
        source_a=fast_source,
        operator=operator,
        source_b=slow_source,
        connector=connector,
        group_id=group_id,
        metadata={
            "scope": scope,
            "source": "crossovers",
            "side": side,
        },
    )


def _build_crossover_rules(
    ready_signals: dict[str, Any],
    scope: str,
) -> list[dict[str, Any]]:
    crossover_config = ready_signals.get("crossovers", {})
    if not crossover_config.get("enabled"):
        return []

    rules: list[dict[str, Any]] = []
    signal_mode = crossover_config.get("signal")
    if signal_mode in {"Cruzamento para compra", "Ambos"}:
        operator = "CROSS_UP" if scope == "entry" else "CROSS_DOWN"
        rules.append(
            _build_crossover_group(
                operator=operator,
                connector=CONNECTOR_START,
                group_id=f"crossovers_buy_{scope}",
                signal_config=crossover_config,
                side="BUY",
                scope=scope,
            )
        )
    if signal_mode in {"Cruzamento para venda", "Ambos"}:
        operator = "CROSS_DOWN" if scope == "entry" else "CROSS_UP"
        rules.append(
            _build_crossover_group(
                operator=operator,
                connector=CONNECTOR_START,
                group_id=f"crossovers_sell_{scope}",
                signal_config=crossover_config,
                side="SELL",
                scope=scope,
            )
        )
    return rules


def _build_bands_inside_outside_rules(
    indicator_name: str,
    parameters: dict[str, Any],
    signal_label: str,
    group_id_prefix: str,
    scope: str,
) -> list[dict[str, Any]]:
    close_current = _make_price_source("close", "Fechamento atual", 0)
    close_previous = _make_price_source("close", "Fechamento anterior", 1)
    upper_current = _make_indicator_source(indicator_name, "Superior", parameters, "Banda superior", 0)
    lower_current = _make_indicator_source(indicator_name, "Inferior", parameters, "Banda inferior", 0)
    upper_previous = _make_indicator_source(indicator_name, "Superior", parameters, "Banda superior", 1)
    lower_previous = _make_indicator_source(indicator_name, "Inferior", parameters, "Banda inferior", 1)

    if signal_label in {"Fechou fora", "Estando fora"}:
        return [
            _make_rule(
                close_current,
                "GREATER_THAN",
                upper_current,
                CONNECTOR_START,
                f"{group_id_prefix}_outside_upper_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_upper"},
            ),
            _make_rule(
                close_current,
                "LESS_THAN",
                lower_current,
                CONNECTOR_START,
                f"{group_id_prefix}_outside_lower_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_lower"},
            ),
        ]

    if signal_label in {"Fechou dentro e saiu", "Fechou dentro e fechou fora"}:
        return [
            _make_rule(
                close_previous,
                "LESS_THAN",
                upper_previous,
                CONNECTOR_START,
                f"{group_id_prefix}_inside_to_upper_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_upper"},
            ),
            _make_rule(
                close_previous,
                "GREATER_THAN",
                lower_previous,
                "E",
                f"{group_id_prefix}_inside_to_upper_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_upper"},
            ),
            _make_rule(
                close_current,
                "GREATER_THAN",
                upper_current,
                "E",
                f"{group_id_prefix}_inside_to_upper_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_upper"},
            ),
            _make_rule(
                close_previous,
                "LESS_THAN",
                upper_previous,
                CONNECTOR_START,
                f"{group_id_prefix}_inside_to_lower_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_lower"},
            ),
            _make_rule(
                close_previous,
                "GREATER_THAN",
                lower_previous,
                "E",
                f"{group_id_prefix}_inside_to_lower_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_lower"},
            ),
            _make_rule(
                close_current,
                "LESS_THAN",
                lower_current,
                "E",
                f"{group_id_prefix}_inside_to_lower_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_lower"},
            ),
        ]

    if signal_label in {"Fechou fora e voltou", "Fechou fora e fechou dentro"}:
        return [
            _make_rule(
                close_previous,
                "GREATER_THAN",
                upper_previous,
                CONNECTOR_START,
                f"{group_id_prefix}_outside_to_inside_upper_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_upper"},
            ),
            _make_rule(
                close_current,
                "LESS_THAN",
                upper_current,
                "E",
                f"{group_id_prefix}_outside_to_inside_upper_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_upper"},
            ),
            _make_rule(
                close_current,
                "GREATER_THAN",
                lower_current,
                "E",
                f"{group_id_prefix}_outside_to_inside_upper_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_upper"},
            ),
            _make_rule(
                close_previous,
                "LESS_THAN",
                lower_previous,
                CONNECTOR_START,
                f"{group_id_prefix}_outside_to_inside_lower_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_lower"},
            ),
            _make_rule(
                close_current,
                "LESS_THAN",
                upper_current,
                "E",
                f"{group_id_prefix}_outside_to_inside_lower_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_lower"},
            ),
            _make_rule(
                close_current,
                "GREATER_THAN",
                lower_current,
                "E",
                f"{group_id_prefix}_outside_to_inside_lower_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_lower"},
            ),
        ]

    return []


def _build_band_channel_rules(
    ready_signals: dict[str, Any],
    scope: str,
) -> list[dict[str, Any]]:
    band_config = ready_signals.get("band_channels", {})
    if not band_config.get("enabled"):
        return []

    signal_label = band_config.get("signal", "Nao usar")
    if scope == "exit":
        signal_label = {
            "Fechou fora": "Fechou fora e voltou",
            "Estando fora": "Fechou fora e voltou",
            "Fechou dentro e saiu": "Fechou fora e voltou",
            "Fechou dentro e fechou fora": "Fechou fora e voltou",
            "Fechou fora e voltou": "Fechou dentro e saiu",
            "Fechou fora e fechou dentro": "Fechou dentro e saiu",
        }.get(signal_label, signal_label)

    indicator_name = band_config.get("indicator", "Bandas de Bollinger")
    if indicator_name == "BBANDS":
        indicator_name = "Bandas de Bollinger"

    parameters = deepcopy(band_config.get("parameters", {}))
    if not parameters:
        parameters = {
            "period": int(band_config.get("period", 20)),
            "deviation": float(band_config.get("deviation", 2.0)),
        }

    if indicator_name == "Donchian":
        parameters = {
            "period": int(parameters.get("period", band_config.get("period", 21))),
        }
    elif indicator_name == "Keltner":
        parameters = {
            "period": int(parameters.get("period", band_config.get("period", 20))),
            "deviation": float(parameters.get("deviation", band_config.get("deviation", 2.0))),
            "ma_type": parameters.get("ma_type", "Exponencial (EMA)"),
        }
    elif indicator_name == "Canal ATR":
        parameters = {
            "period": int(parameters.get("period", band_config.get("period", 14))),
            "deviation": float(parameters.get("deviation", band_config.get("deviation", 2.0))),
            "price_mode": parameters.get("price_mode", "Fechamento"),
        }
    elif indicator_name == "Envelopes":
        parameters = {
            "period": int(parameters.get("period", band_config.get("period", 14))),
            "deviation": float(parameters.get("deviation", band_config.get("deviation", 1.0))),
            "displacement": int(parameters.get("displacement", 0)),
            "ma_type": parameters.get("ma_type", "Simples (SMA)"),
            "price_mode": parameters.get("price_mode", "Fechamento"),
        }
    else:
        parameters = {
            "period": int(parameters.get("period", band_config.get("period", 20))),
            "deviation": float(parameters.get("deviation", band_config.get("deviation", 2.0))),
            "displacement": int(parameters.get("displacement", 0)),
            "price_mode": parameters.get("price_mode", "Fechamento"),
        }

    return _build_bands_inside_outside_rules(
        indicator_name=indicator_name,
        parameters=parameters,
        signal_label=signal_label,
        group_id_prefix="band_channels",
        scope=scope,
    )


def _build_level_rules(
    indicator_name: str,
    parameters: dict[str, Any],
    output_name: str,
    signal_label: str,
    upper_level: float,
    lower_level: float,
    group_id_prefix: str,
    scope: str,
) -> list[dict[str, Any]]:
    indicator_current = _make_indicator_source(indicator_name, output_name, parameters, indicator_name, 0)
    indicator_previous = _make_indicator_source(indicator_name, output_name, parameters, indicator_name, 1)
    upper_source = _make_fixed_source(upper_level, f"Nivel {upper_level}")
    lower_source = _make_fixed_source(lower_level, f"Nivel {lower_level}")

    if signal_label in {"Fechou fora", "Estando fora"}:
        return [
            _make_rule(
                indicator_current,
                "GREATER_THAN",
                upper_source,
                CONNECTOR_START,
                f"{group_id_prefix}_above_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "above"},
            ),
            _make_rule(
                indicator_current,
                "LESS_THAN",
                lower_source,
                CONNECTOR_START,
                f"{group_id_prefix}_below_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "below"},
            ),
        ]

    if signal_label in {"Fechou dentro e saiu", "Fechou dentro e fechou fora"}:
        return [
            _make_rule(
                indicator_previous,
                "LESS_THAN",
                upper_source,
                CONNECTOR_START,
                f"{group_id_prefix}_inside_to_above_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_above"},
            ),
            _make_rule(
                indicator_previous,
                "GREATER_THAN",
                lower_source,
                "E",
                f"{group_id_prefix}_inside_to_above_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_above"},
            ),
            _make_rule(
                indicator_current,
                "GREATER_THAN",
                upper_source,
                "E",
                f"{group_id_prefix}_inside_to_above_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_above"},
            ),
            _make_rule(
                indicator_previous,
                "LESS_THAN",
                upper_source,
                CONNECTOR_START,
                f"{group_id_prefix}_inside_to_below_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_below"},
            ),
            _make_rule(
                indicator_previous,
                "GREATER_THAN",
                lower_source,
                "E",
                f"{group_id_prefix}_inside_to_below_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_below"},
            ),
            _make_rule(
                indicator_current,
                "LESS_THAN",
                lower_source,
                "E",
                f"{group_id_prefix}_inside_to_below_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "inside_to_below"},
            ),
        ]

    if signal_label in {"Fechou fora e voltou", "Fechou fora e fechou dentro"}:
        return [
            _make_rule(
                indicator_previous,
                "GREATER_THAN",
                upper_source,
                CONNECTOR_START,
                f"{group_id_prefix}_outside_to_inside_above_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_above"},
            ),
            _make_rule(
                indicator_current,
                "LESS_THAN",
                upper_source,
                "E",
                f"{group_id_prefix}_outside_to_inside_above_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_above"},
            ),
            _make_rule(
                indicator_current,
                "GREATER_THAN",
                lower_source,
                "E",
                f"{group_id_prefix}_outside_to_inside_above_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_above"},
            ),
            _make_rule(
                indicator_previous,
                "LESS_THAN",
                lower_source,
                CONNECTOR_START,
                f"{group_id_prefix}_outside_to_inside_below_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_below"},
            ),
            _make_rule(
                indicator_current,
                "LESS_THAN",
                upper_source,
                "E",
                f"{group_id_prefix}_outside_to_inside_below_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_below"},
            ),
            _make_rule(
                indicator_current,
                "GREATER_THAN",
                lower_source,
                "E",
                f"{group_id_prefix}_outside_to_inside_below_{scope}",
                {"scope": scope, "source": group_id_prefix, "variant": "outside_to_inside_below"},
            ),
        ]

    return []


def _build_overbought_oversold_rules(
    ready_signals: dict[str, Any],
    scope: str,
) -> list[dict[str, Any]]:
    signal_config = ready_signals.get("overbought_oversold", {})
    if not signal_config.get("enabled"):
        return []

    signal_label = signal_config.get("signal", "Nao usar")
    if scope == "exit":
        signal_label = {
            "Fechou fora": "Fechou fora e voltou",
            "Estando fora": "Fechou fora e voltou",
            "Fechou dentro e saiu": "Fechou fora e voltou",
            "Fechou dentro e fechou fora": "Fechou fora e voltou",
            "Fechou fora e voltou": "Fechou dentro e saiu",
            "Fechou fora e fechou dentro": "Fechou dentro e saiu",
        }.get(signal_label, signal_label)

    indicator_name = signal_config.get("indicator", "RSI (Relative Strength Index)")
    if indicator_name == "RSI":
        indicator_name = "RSI (Relative Strength Index)"
    if indicator_name == "CCI":
        indicator_name = "CCI (Commodity Channel Index)"

    parameters = deepcopy(signal_config.get("parameters", {}))
    if not parameters and signal_config.get("period") is not None:
        parameters = {"period": int(signal_config.get("period", 14))}

    return _build_level_rules(
        indicator_name=indicator_name,
        parameters=parameters,
        output_name=signal_config.get("indicator_output", "Valor"),
        signal_label=signal_label,
        upper_level=float(signal_config.get("overbought_level", 70)),
        lower_level=float(signal_config.get("oversold_level", 30)),
        group_id_prefix="overbought_oversold",
        scope=scope,
    )


def build_entry_rules(ready_signals: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *_build_manual_rules(ready_signals, scope="entry"),
        *_build_crossover_rules(ready_signals, scope="entry"),
        *_build_band_channel_rules(ready_signals, scope="entry"),
        *_build_overbought_oversold_rules(ready_signals, scope="entry"),
    ]


def build_exit_rules(ready_signals: dict[str, Any]) -> list[dict[str, Any]]:
    manual_entry_rules = _build_manual_rules(ready_signals, scope="entry")
    manual_exit_rules = [
        _invert_rule(rule, scope="exit")
        for rule in manual_entry_rules
    ]
    manual_exit_rules = _normalize_connectors(manual_exit_rules)

    return [
        *manual_exit_rules,
        *_build_crossover_rules(ready_signals, scope="exit"),
        *_build_band_channel_rules(ready_signals, scope="exit"),
        *_build_overbought_oversold_rules(ready_signals, scope="exit"),
    ]
