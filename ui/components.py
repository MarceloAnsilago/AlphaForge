from __future__ import annotations

import streamlit as st

from config import (
    INITIAL_INDICATORS,
    OPERATORS,
    PENDING_PRICE_REFERENCE_OPTIONS,
    PRICE_FIELDS,
    STOP_CANDLE_REFERENCE_OPTIONS,
    STOP_TYPES,
    YES_NO_OPTIONS,
)
from utils.helpers import (
    build_operand,
    build_source_options,
    format_source_option,
    humanize_rule_name,
    parse_source_option,
)


RULE_SOURCE_OPTIONS = build_source_options(INITIAL_INDICATORS, PRICE_FIELDS)
PRICE_SOURCE_OPTIONS = [option for option in RULE_SOURCE_OPTIONS if option.startswith("PRICE:")]
INDICATOR_SOURCE_OPTIONS = [
    option for option in RULE_SOURCE_OPTIONS if option.startswith("INDICATOR:")
]

RIGHT_OPERAND_TYPES = {
    "price": "Preco",
    "indicator": "Indicador",
    "fixed": "Valor fixo",
}

STOP_MEDIA_REFERENCE_OPTIONS = ["Maxima", "Minima", "Abertura", "Fechamento"]
STOP_MULTIPLY_REFERENCE_OPTIONS = ["Corpo", "Pavios"]


def _format_distance_type(value: str) -> str:
    return "Pontos" if value == "points" else "Percentual"


def _format_stop_reference_example(mode: str, candle_count: int, reference: str) -> str:
    count_words = {
        1: "uma",
        2: "duas",
        3: "tres",
        4: "quatro",
        5: "cinco",
        6: "seis",
        7: "sete",
        8: "oito",
        9: "nove",
        10: "dez",
    }
    plural_references = {
        "Maxima": "maximas",
        "Minima": "minimas",
        "Abertura": "aberturas",
        "Fechamento": "fechamentos",
        "Corpo": "corpos",
        "Pavios": "pavios",
    }

    count_label = count_words.get(candle_count, str(candle_count))
    reference_label = plural_references.get(reference, reference.lower())

    if mode == "Media":
        return f"Ex.: media das {count_label} ultimas {reference_label}."

    return "Ex.: 1 = primeiro candle, 2 = segundo candle, 3 = terceiro candle."


def render_regra(prefix: str) -> dict:
    with st.expander(humanize_rule_name(prefix), expanded=False):
        left_source = st.selectbox(
            "Indicador ou preco",
            options=RULE_SOURCE_OPTIONS,
            format_func=format_source_option,
            key=f"{prefix}_left_source",
        )
        left_parsed = parse_source_option(left_source)

        left_period = None
        if left_parsed["kind"] == "indicator":
            left_period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=f"{prefix}_left_period",
            )

        operator = st.selectbox(
            "Operador",
            options=list(OPERATORS.keys()),
            format_func=lambda value: OPERATORS[value],
            key=f"{prefix}_operator",
        )
        candle_offset = st.selectbox(
            "Candle offset",
            options=[0, 1, 2],
            key=f"{prefix}_offset",
        )
        comparator_type = st.selectbox(
            "Comparar com",
            options=list(RIGHT_OPERAND_TYPES.keys()),
            format_func=lambda value: RIGHT_OPERAND_TYPES[value],
            key=f"{prefix}_right_type",
        )

        right_period = None
        if comparator_type == "fixed":
            fixed_value = st.number_input(
                "Valor fixo",
                value=0.0,
                step=0.1,
                key=f"{prefix}_fixed_value",
            )
            right_operand = build_operand("fixed", fixed_value)
        else:
            source_options = (
                INDICATOR_SOURCE_OPTIONS if comparator_type == "indicator" else PRICE_SOURCE_OPTIONS
            )
            right_source = st.selectbox(
                "Outro indicador ou preco",
                options=source_options,
                format_func=format_source_option,
                key=f"{prefix}_right_source",
            )
            right_parsed = parse_source_option(right_source)
            if comparator_type == "indicator":
                right_period = st.number_input(
                    "Periodo do comparador",
                    min_value=1,
                    value=14,
                    step=1,
                    key=f"{prefix}_right_period",
                )
                right_operand = build_operand(
                    "indicator",
                    right_parsed["name"],
                    right_period,
                )
            else:
                right_operand = build_operand("price", right_parsed["name"])

        left_operand = build_operand(
            left_parsed["kind"],
            left_parsed["name"],
            left_period,
        )

        return {
            "left": left_operand,
            "operator": operator,
            "right": right_operand,
            "candle_offset": candle_offset,
        }


def render_stop_loss() -> dict:
    stop_enabled = st.radio(
        "Usar stop loss?",
        options=YES_NO_OPTIONS,
        key="custom_stop_loss",
        horizontal=True,
    )
    stop_type = STOP_TYPES[0]
    stop_mode = "Calculo"
    stop_reference = PENDING_PRICE_REFERENCE_OPTIONS[0]
    stop_candle = STOP_CANDLE_REFERENCE_OPTIONS[0]
    stop_candle_period = 1
    stop_candle_reference = PENDING_PRICE_REFERENCE_OPTIONS[0]
    stop_multiplier = 1.0
    stop_value = 0.0

    if stop_enabled == "Sim":
        stop_type = st.selectbox(
            "Tipo de stop",
            options=STOP_TYPES,
            format_func=_format_distance_type,
            key="risk_stop_type",
        )
        stop_mode = st.radio(
            "Modo do stop",
            options=["Calculo", "Fixo"],
            key="risk_stop_mode",
            horizontal=True,
        )
        if stop_mode == "Calculo":
            stop_reference = st.selectbox(
                "Referencia de preco",
                options=PENDING_PRICE_REFERENCE_OPTIONS,
                key="risk_stop_reference",
            )
            stop_candle = st.selectbox(
                "Candle",
                options=STOP_CANDLE_REFERENCE_OPTIONS,
                key="risk_stop_candle",
            )
            if stop_candle == "Media":
                candle_period_col, candle_reference_col = st.columns(2)
                with candle_period_col:
                    stop_candle_period = st.number_input(
                        "Qtd candle",
                        min_value=1,
                        value=3,
                        step=1,
                        key="risk_stop_candle_period",
                    )
                with candle_reference_col:
                    current_stop_reference = st.session_state.get("risk_stop_candle_reference")
                    if current_stop_reference not in STOP_MEDIA_REFERENCE_OPTIONS:
                        st.session_state["risk_stop_candle_reference"] = STOP_MEDIA_REFERENCE_OPTIONS[0]
                    stop_candle_reference = st.selectbox(
                        "Base da referencia",
                        options=STOP_MEDIA_REFERENCE_OPTIONS,
                        key="risk_stop_candle_reference",
                    )
                st.caption(
                    _format_stop_reference_example(
                        stop_candle,
                        int(stop_candle_period),
                        stop_candle_reference,
                    )
                )
            elif stop_candle == "Multiplicar":
                multiply_reference_col, multiply_candle_col, multiplier_col = st.columns(3)
                with multiply_reference_col:
                    current_stop_reference = st.session_state.get("risk_stop_candle_reference")
                    if current_stop_reference not in STOP_MULTIPLY_REFERENCE_OPTIONS:
                        st.session_state["risk_stop_candle_reference"] = STOP_MULTIPLY_REFERENCE_OPTIONS[0]
                    stop_candle_reference = st.selectbox(
                        "Base da referencia",
                        options=STOP_MULTIPLY_REFERENCE_OPTIONS,
                        key="risk_stop_candle_reference",
                    )
                with multiply_candle_col:
                    stop_candle_period = st.number_input(
                        "Candle",
                        min_value=1,
                        value=1,
                        step=1,
                        key="risk_stop_candle_period",
                    )
                with multiplier_col:
                    stop_multiplier = st.number_input(
                        "Multiplicador",
                        min_value=0.0,
                        value=1.0,
                        step=0.1,
                        key="risk_stop_multiplier",
                    )
                st.caption(
                    _format_stop_reference_example(
                        stop_candle,
                        int(stop_candle_period),
                        stop_candle_reference,
                    )
                )
        else:
            stop_value = st.number_input(
                "Distancia do stop",
                min_value=0.0,
                value=100.0,
                step=1.0,
                key="risk_stop_value",
            )

    return {
        "enabled": stop_enabled == "Sim",
        "mode": stop_mode,
        "reference": stop_reference,
        "candle": stop_candle,
        "candle_period": int(stop_candle_period),
        "candle_reference": stop_candle_reference,
        "multiplier": float(stop_multiplier),
        "target": {
            "type": stop_type,
            "value": float(stop_value),
        },
    }


def render_take_profit() -> dict:
    take_enabled = st.radio(
        "Usar take profit?",
        options=YES_NO_OPTIONS,
        key="custom_take_profit",
        horizontal=True,
    )
    take_type = STOP_TYPES[0]
    take_value = 0.0

    if take_enabled == "Sim":
        take_type = st.selectbox(
            "Tipo de take",
            options=STOP_TYPES,
            format_func=_format_distance_type,
            key="risk_take_type",
        )
        take_value = st.number_input(
            "Distancia do take",
            min_value=0.0,
            value=100.0,
            step=1.0,
            key="risk_take_value",
        )

    return {
        "enabled": take_enabled == "Sim",
        "target": {
            "type": take_type,
            "value": float(take_value),
        },
    }


def render_stop_movel() -> dict:
    stop_movel_enabled = st.radio(
        "Usar stop movel?",
        options=YES_NO_OPTIONS,
        key="custom_stop_movel",
        horizontal=True,
    )
    stop_movel_type = STOP_TYPES[0]
    stop_movel_distance = 0.0

    if stop_movel_enabled == "Sim":
        stop_movel_type = st.selectbox(
            "Tipo do stop movel",
            options=STOP_TYPES,
            format_func=_format_distance_type,
            key="stop_movel_type",
        )
        stop_movel_distance = st.number_input(
            "Distancia do stop movel",
            min_value=0.0,
            value=50.0,
            step=1.0,
            key="stop_movel_distance",
        )

    return {
        "enabled": stop_movel_enabled == "Sim",
        "type": stop_movel_type,
        "distance": float(stop_movel_distance),
    }


def render_trailing_stop() -> dict:
    trailing_stop_enabled = st.radio(
        "Usar trailing stop?",
        options=YES_NO_OPTIONS,
        key="custom_trailing_stop",
        horizontal=True,
    )
    trailing_stop_type = STOP_TYPES[0]
    trailing_stop_distance = 0.0

    if trailing_stop_enabled == "Sim":
        trailing_stop_type = st.selectbox(
            "Tipo do trailing stop",
            options=STOP_TYPES,
            format_func=_format_distance_type,
            key="trailing_stop_type",
        )
        trailing_stop_distance = st.number_input(
            "Distancia do trailing stop",
            min_value=0.0,
            value=50.0,
            step=1.0,
            key="trailing_stop_distance",
        )

    return {
        "enabled": trailing_stop_enabled == "Sim",
        "type": trailing_stop_type,
        "distance": float(trailing_stop_distance),
    }
