from __future__ import annotations

from typing import Any

import streamlit as st

from config import (
    ORDER_EXECUTION_OPTIONS,
    PENDING_CANDLE_REFERENCE_OPTIONS,
    PENDING_EXPIRATION_OPTIONS,
    PENDING_POSITION_OPTIONS,
    PENDING_PRICE_REFERENCE_OPTIONS,
)
from state import get_state


def _order_side_label(prefix: str) -> str:
    side_labels = {
        "entry": "entrada",
        "exit": "saida",
    }
    return side_labels.get(prefix, prefix)


def _flatten_pending_config(prefix: str, order_config: dict[str, Any]) -> dict[str, Any]:
    pending_config = order_config.get("pending", {})
    return {
        f"{prefix}_order_type": order_config["order_type"],
        f"{prefix}_pending_positioning": pending_config.get("positioning"),
        f"{prefix}_pending_average_candles": pending_config.get("average_candles"),
        f"{prefix}_pending_price_reference": pending_config.get("price_reference"),
        f"{prefix}_pending_candle_reference": pending_config.get("candle_reference"),
        f"{prefix}_pending_order_distance": pending_config.get("distance"),
        f"{prefix}_pending_expiration": pending_config.get("expiration"),
    }


def build_time_config(
    close_by_schedule: str,
    close_hour: int,
    close_minute: int,
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
) -> dict[str, Any]:
    return {
        "close_by_schedule": close_by_schedule == "Sim",
        "operation_start_time": f"{start_hour:02d}:{start_minute:02d}",
        "operation_end_time": f"{end_hour:02d}:{end_minute:02d}",
        "close_operations_time": f"{close_hour:02d}:{close_minute:02d}",
    }


def build_order_config(prefix: str) -> dict[str, Any]:
    state = get_state()
    distance_calculation_type = state.get("distance_calculation_type", "Pontos")
    distance_step = 1.0 if distance_calculation_type == "Pontos" else 0.1
    side_label = _order_side_label(prefix)

    order_type = st.selectbox(
        f"Ordem de {side_label}",
        options=ORDER_EXECUTION_OPTIONS,
        key=f"{prefix}_order_type",
    )
    order_config: dict[str, Any] = {
        "order_type": order_type,
        "pending": {},
    }

    if order_type != "Pendente":
        return order_config

    positioning = st.selectbox(
        "Posicionar",
        options=PENDING_POSITION_OPTIONS,
        key=f"{prefix}_pending_positioning",
    )
    pending_config: dict[str, Any] = {
        "positioning": positioning,
    }

    if positioning == "Media":
        pending_config["average_candles"] = int(
            st.number_input(
                "Quantidade de candles para media",
                min_value=1,
                value=3,
                step=1,
                key=f"{prefix}_pending_average_candles",
            )
        )

    pending_config["price_reference"] = st.selectbox(
        "Referencia de preco",
        options=PENDING_PRICE_REFERENCE_OPTIONS,
        key=f"{prefix}_pending_price_reference",
    )

    if positioning == "Referencia de preco":
        pending_config["candle_reference"] = st.selectbox(
            "Candle",
            options=PENDING_CANDLE_REFERENCE_OPTIONS,
            key=f"{prefix}_pending_candle_reference",
        )

    pending_config["distance"] = float(
        st.number_input(
            f"Distancia da ordem ({distance_calculation_type})",
            min_value=0.0,
            value=0.0,
            step=distance_step,
            key=f"{prefix}_pending_order_distance",
        )
    )
    pending_config["expiration"] = st.selectbox(
        "Expiracao da ordem em candles futuros",
        options=PENDING_EXPIRATION_OPTIONS,
        format_func=lambda value: value if value == "Nao expirar" else f"{value} candle(s)",
        key=f"{prefix}_pending_expiration",
    )

    order_config["pending"] = pending_config
    return order_config


def build_settings(
    operation_config: dict[str, Any],
    time_config: dict[str, Any],
    risk_config: dict[str, Any],
    execution_config: dict[str, Any],
    filter_config: dict[str, Any],
    ready_signals: dict[str, Any],
    final_adjustments: dict[str, Any],
    initial_setup_config: dict[str, Any],
) -> dict[str, Any]:
    operation_settings = {
        "operate_buy": operation_config["operate_buy"],
        "operate_sell": operation_config["operate_sell"],
        "desired_market": operation_config["desired_market"],
        "operational_type": operation_config["operational_type"],
        "processing_mode": operation_config["processing_mode"],
        **time_config,
        "primary_timeframe": initial_setup_config["primary_timeframe"],
        "initial_volume": initial_setup_config["initial_volume"],
        "max_spread": initial_setup_config["max_spread"],
    }

    stop_loss_config = risk_config["stop_loss"]
    soft_trailing_stop_config = risk_config["soft_trailing_stop"]
    take_profit_config = risk_config["take_profit"]
    trailing_stop_config = risk_config["trailing_stop"]
    partial_exits_config = risk_config["partial_exits"]

    risk_settings = {
        "custom_stop_loss": stop_loss_config["enabled"],
        "stop_loss_mode": stop_loss_config["mode"],
        "stop_loss_calculation_type": stop_loss_config["calculation_type"],
        "stop_loss_calculation_method": stop_loss_config["calculation_method"],
        "stop_loss_reference": stop_loss_config["reference"],
        "stop_loss_candle": stop_loss_config["candle"],
        "stop_loss_candle_period": stop_loss_config["candle_period"],
        "stop_loss_candle_reference": stop_loss_config["candle_reference"],
        "stop_loss_multiplier": stop_loss_config["multiplier"],
        "custom_take_profit": take_profit_config["enabled"],
        "take_profit_type": take_profit_config["target"]["type"],
        "custom_stop_movel": soft_trailing_stop_config["enabled"],
        "stop_movel_calculation_type": soft_trailing_stop_config["calculation_type"],
        "stop_movel_type": soft_trailing_stop_config["type"],
        "stop_movel_acionar_a_favor": soft_trailing_stop_config["acionar_a_favor"],
        "stop_movel_passe": soft_trailing_stop_config["passe"],
        "stop_movel_candles_basis": soft_trailing_stop_config["candles_basis"],
        "stop_movel_distance": soft_trailing_stop_config["distance"],
        "stop_movel_candle_count": soft_trailing_stop_config["candle_count"],
        "stop_movel_reference": soft_trailing_stop_config["reference"],
        "stop_movel_indicator": soft_trailing_stop_config["indicator"],
        "custom_trailing_stop": trailing_stop_config["enabled"],
        "trailing_stop_calculation_type": trailing_stop_config["calculation_type"],
        "trailing_stop_type": trailing_stop_config["type"],
        "trailing_stop_acionar_a_favor": trailing_stop_config["acionar_a_favor"],
        "trailing_stop_passe": trailing_stop_config["passe"],
        "trailing_stop_candles_basis": trailing_stop_config["candles_basis"],
        "trailing_stop_distance": trailing_stop_config["distance"],
        "trailing_stop_candle_count": trailing_stop_config["candle_count"],
        "trailing_stop_reference": trailing_stop_config["reference"],
        "trailing_stop_indicator": trailing_stop_config["indicator"],
        "custom_partial_exits": partial_exits_config["enabled"],
        "partial_exits_calculation_type": partial_exits_config["calculation_type"],
        "partial_exits_levels": partial_exits_config["levels"],
        "ready_signals": ready_signals,
        "final_adjustments": final_adjustments,
    }

    entry_order_config = execution_config["entry"]
    exit_order_config = execution_config["exit"]
    execution_settings = {
        "distance_calculation_type": execution_config["distance_calculation_type"],
        **_flatten_pending_config("entry", entry_order_config),
        **_flatten_pending_config("exit", exit_order_config),
    }

    candle_constraints = filter_config["candle_constraints"]
    filter_settings = {
        "candle_filter_timeframe": candle_constraints["timeframe"],
        "candle_filter_measure_type": candle_constraints["measure_type"],
        "candle_filter_min_size": candle_constraints["min_size"],
        "candle_filter_max_size": candle_constraints["max_size"],
        "candle_filter_min_body": candle_constraints["min_body"],
        "candle_filter_max_body": candle_constraints["max_body"],
    }

    return {
        **operation_settings,
        **risk_settings,
        **execution_settings,
        **filter_settings,
    }
