from __future__ import annotations

import streamlit as st

from config import (
    INITIAL_INDICATORS,
    OPERATORS,
    PRICE_FIELDS,
    STOP_TYPES,
    TAKE_TYPES,
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
    stop_customized = st.selectbox(
        "Stop loss personalizado",
        options=YES_NO_OPTIONS,
        key="custom_stop_loss",
    )
    stop_type = STOP_TYPES[0]
    stop_value = 0.0

    if stop_customized == "Sim":
        stop_type = st.selectbox(
            "Tipo de stop",
            options=STOP_TYPES,
            format_func=lambda value: "Pontos" if value == "points" else value,
            key="risk_stop_type",
        )
        stop_value = st.number_input(
            "Valor do stop",
            min_value=0.0,
            value=100.0,
            step=1.0,
            key="risk_stop_value",
        )
    else:
        st.caption("Stop loss desativado.")

    return {
        "enabled": stop_customized == "Sim",
        "target": {
            "type": stop_type,
            "value": float(stop_value),
        },
    }


def render_take_profit() -> dict:
    take_customized = st.selectbox(
        "Take profit personalizado",
        options=YES_NO_OPTIONS,
        key="custom_take_profit",
    )
    take_type = TAKE_TYPES[0]
    take_value = 0.0

    if take_customized == "Sim":
        take_type = st.selectbox(
            "Tipo de take",
            options=TAKE_TYPES,
            format_func=lambda value: "Fixo" if value == "fixed" else value,
            key="risk_take_type",
        )
        take_value = st.number_input(
            "Valor do take",
            min_value=0.0,
            value=2.0,
            step=0.1,
            key="risk_take_value",
        )
    else:
        st.caption("Take profit desativado.")

    return {
        "enabled": take_customized == "Sim",
        "target": {
            "type": take_type,
            "value": float(take_value),
        },
    }


def render_stop_movel() -> dict:
    stop_movel_enabled = st.selectbox(
        "Stop movel personalizado",
        options=YES_NO_OPTIONS,
        key="custom_stop_movel",
    )
    stop_movel_distance = 0.0

    if stop_movel_enabled == "Sim":
        stop_movel_distance = st.number_input(
            "Distancia do stop movel",
            min_value=0.0,
            value=50.0,
            step=1.0,
            key="stop_movel_distance",
        )
    else:
        st.caption("Stop movel desativado.")

    return {
        "enabled": stop_movel_enabled == "Sim",
        "distance": float(stop_movel_distance),
    }


def render_trailing_stop() -> dict:
    trailing_stop_enabled = st.selectbox(
        "Trailing stop personalizado",
        options=YES_NO_OPTIONS,
        key="custom_trailing_stop",
    )
    trailing_stop_distance = 0.0

    if trailing_stop_enabled == "Sim":
        trailing_stop_distance = st.number_input(
            "Distancia do trailing stop",
            min_value=0.0,
            value=50.0,
            step=1.0,
            key="trailing_stop_distance",
        )
    else:
        st.caption("Trailing stop desativado.")

    return {
        "enabled": trailing_stop_enabled == "Sim",
        "distance": float(trailing_stop_distance),
    }
