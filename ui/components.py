from __future__ import annotations

import streamlit as st

from config import (
    INITIAL_INDICATORS,
    OPERATORS,
    PENDING_PRICE_REFERENCE_OPTIONS,
    PRICE_FIELDS,
    STOP_CALCULATION_OPTIONS,
    STOP_CANDLE_REFERENCE_OPTIONS,
    STOP_MOVEL_MODE_OPTIONS,
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
STOP_PRICE_REFERENCE_OPTIONS = ["Maxima", "Minima", "Abertura", "Fechamento"]
BAND_CHANNEL_INDICATOR_OPTIONS = ["BBANDS"]
CROSSOVER_INDICATOR_OPTIONS = ["SMA", "EMA"]
OVERBOUGHT_OVERSOLD_INDICATOR_OPTIONS = ["RSI", "CCI"]
READY_SIGNAL_INDICATOR_OPTIONS = [
    "Nao usar",
    "Externo",
    "Keltner",
    "Donchian",
    "Regressao",
    "Afastamento da media",
    "Desvio Medio",
    "Canal ATR",
    "Media Movel",
    "Bandas de Bollinger",
    "MACD",
    "Envelopes",
    "Estocastico",
    "RSI (Relative Strength Index)",
    "Desvio Padrao",
    "Volume",
    "ATR (Average True Range)",
    "Parabolic SAR",
    "Fractal",
    "OBV (On Balance Volume)",
    "Acumulacao/Distribuicao (A/D)",
    "MFI (Money Flow Index)",
    "Vidya",
    "DEMA",
    "TEMA",
    "FRAMA",
    "TRIX",
    "Bears Power",
    "Bulls Power",
    "Chaikin Oscilador",
    "Accelerator Oscillator",
    "Awesome Oscillator",
    "CCI (Commodity Channel Index)",
    "DeMarker",
    "Alligator",
    "Nuvem de Ichimoku",
    "ADX (Average Directional Index)",
    "ADX Welles Wilder",
    "Gator Oscillator",
    "Williams %R (WPR)",
    "Market Facilitation Index",
    "Momentum",
    "RVI (Relative Vigor Index)",
]


def _format_distance_type(value: str) -> str:
    return "Pontos" if value == "points" else "Percentual"


def _format_stop_movel_mode(value: str) -> str:
    mode_labels = {
        "padrao": "Padrao",
        "candles": "Candles",
        "indicator": "Indicador",
    }
    return mode_labels.get(value, value)


def _format_stop_movel_candles_basis(value: str) -> str:
    basis_labels = {
        "distance": "Distancia",
        "candle_count": "Numero de candles",
    }
    return basis_labels.get(value, value)


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


def _render_stop_reference_note() -> None:
    st.caption(
        "A referencia exibida considera a compra. Na venda, os valores se invertem automaticamente: maxima vira minima e minima vira maxima."
    )


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
    stop_calculation_type = "Referencia de preco"
    stop_calculation_method = STOP_CALCULATION_OPTIONS[0]
    stop_reference = STOP_PRICE_REFERENCE_OPTIONS[0]
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
        if stop_type == "percentual":
            stop_mode = "Fixo"
            st.caption("Stop percentual aceita apenas o modo fixo.")
        else:
            stop_mode = st.radio(
                "Modo do stop",
                options=["Calculo", "Fixo"],
                key="risk_stop_mode",
                horizontal=True,
            )

        if stop_mode == "Calculo":
            stop_calculation_type = st.selectbox(
                "Tipo",
                options=["Calculo", "Referencia de preco"],
                key="risk_stop_calculation_type",
            )
            if stop_calculation_type == "Referencia de preco":
                stop_reference = st.selectbox(
                    "Referencia de preco",
                    options=STOP_PRICE_REFERENCE_OPTIONS,
                    key="risk_stop_reference",
                )
                current_stop_candle = st.session_state.get("risk_stop_candle")
                if current_stop_candle not in STOP_CANDLE_REFERENCE_OPTIONS:
                    st.session_state["risk_stop_candle"] = STOP_CANDLE_REFERENCE_OPTIONS[0]
                stop_candle = st.selectbox(
                    "Candle",
                    options=STOP_CANDLE_REFERENCE_OPTIONS,
                    key="risk_stop_candle",
                )
                _render_stop_reference_note()
            else:
                stop_calculation_method = st.selectbox(
                    "Calculo",
                    options=STOP_CALCULATION_OPTIONS,
                    key="risk_stop_calculation_method",
                )
            if stop_calculation_method == "Media" and stop_calculation_type == "Calculo":
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
                        stop_calculation_method,
                        int(stop_candle_period),
                        stop_candle_reference,
                    )
                )
                _render_stop_reference_note()
            elif stop_calculation_method == "Multiplicar" and stop_calculation_type == "Calculo":
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
                        stop_calculation_method,
                        int(stop_candle_period),
                        stop_candle_reference,
                    )
                )
                _render_stop_reference_note()
        else:
            stop_value = st.number_input(
                "Distancia do stop",
                min_value=0.0,
                value=100.0 if stop_type == "points" else 1.0,
                step=1.0 if stop_type == "points" else 0.1,
                key="risk_stop_value",
            )

    return {
        "enabled": stop_enabled == "Sim",
        "mode": stop_mode,
        "calculation_type": stop_calculation_type,
        "calculation_method": stop_calculation_method,
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
    stop_movel_calculation_type = STOP_TYPES[0]
    stop_movel_type = STOP_MOVEL_MODE_OPTIONS[0]
    stop_movel_acionar_a_favor = 0.0
    stop_movel_passe = 0.0
    stop_movel_candles_basis = "distance"
    stop_movel_distance = 0.0
    stop_movel_candle_count = 1
    stop_movel_reference = STOP_PRICE_REFERENCE_OPTIONS[0]
    stop_movel_indicator = INITIAL_INDICATORS[0]

    if stop_movel_enabled == "Sim":
        stop_movel_calculation_type = st.selectbox(
            "Calculo",
            options=STOP_TYPES,
            format_func=_format_distance_type,
            key="stop_movel_calculation_type",
        )
        stop_movel_type = st.selectbox(
            "Tipo",
            options=STOP_MOVEL_MODE_OPTIONS,
            format_func=_format_stop_movel_mode,
            key="stop_movel_type",
        )

        if stop_movel_type == "padrao":
            stop_movel_acionar_a_favor = st.number_input(
                "Acionar a favor",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="stop_movel_acionar_a_favor",
            )
            stop_movel_passe = st.number_input(
                "Passe",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="stop_movel_passe",
            )
        elif stop_movel_type == "candles":
            stop_movel_candles_basis = st.selectbox(
                "Base",
                options=["distance", "candle_count"],
                format_func=_format_stop_movel_candles_basis,
                key="stop_movel_candles_basis",
            )
            if stop_movel_candles_basis == "distance":
                stop_movel_distance = st.number_input(
                    "Distancia",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key="stop_movel_distance",
                )
            else:
                stop_movel_candle_count = st.number_input(
                    "Numero de candles",
                    min_value=1,
                    value=1,
                    step=1,
                    key="stop_movel_candle_count",
                )
            stop_movel_reference = st.selectbox(
                "Posicionar em",
                options=STOP_PRICE_REFERENCE_OPTIONS,
                key="stop_movel_reference",
            )
        elif stop_movel_type == "indicator":
            stop_movel_indicator = st.selectbox(
                "Indicador",
                options=INITIAL_INDICATORS,
                key="stop_movel_indicator",
            )

    return {
        "enabled": stop_movel_enabled == "Sim",
        "calculation_type": stop_movel_calculation_type,
        "type": stop_movel_type,
        "acionar_a_favor": float(stop_movel_acionar_a_favor),
        "passe": float(stop_movel_passe),
        "candles_basis": stop_movel_candles_basis,
        "distance": float(stop_movel_distance),
        "candle_count": int(stop_movel_candle_count),
        "reference": stop_movel_reference,
        "indicator": stop_movel_indicator,
    }


def render_trailing_stop() -> dict:
    trailing_stop_enabled = st.radio(
        "Usar trailing stop?",
        options=YES_NO_OPTIONS,
        key="custom_trailing_stop",
        horizontal=True,
    )
    trailing_stop_calculation_type = STOP_TYPES[0]
    trailing_stop_type = STOP_MOVEL_MODE_OPTIONS[0]
    trailing_stop_acionar_a_favor = 0.0
    trailing_stop_passe = 0.0
    trailing_stop_candles_basis = "distance"
    trailing_stop_distance = 0.0
    trailing_stop_candle_count = 1
    trailing_stop_reference = STOP_PRICE_REFERENCE_OPTIONS[0]
    trailing_stop_indicator = INITIAL_INDICATORS[0]

    if trailing_stop_enabled == "Sim":
        trailing_stop_calculation_type = st.selectbox(
            "Calculo",
            options=STOP_TYPES,
            format_func=_format_distance_type,
            key="trailing_stop_calculation_type",
        )
        trailing_stop_type = st.selectbox(
            "Tipo",
            options=STOP_MOVEL_MODE_OPTIONS,
            format_func=_format_stop_movel_mode,
            key="trailing_stop_type",
        )

        if trailing_stop_type == "padrao":
            trailing_stop_acionar_a_favor = st.number_input(
                "Acionar a favor",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="trailing_stop_acionar_a_favor",
            )
            trailing_stop_passe = st.number_input(
                "Passe",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="trailing_stop_passe",
            )
        elif trailing_stop_type == "candles":
            trailing_stop_candles_basis = st.selectbox(
                "Base",
                options=["distance", "candle_count"],
                format_func=_format_stop_movel_candles_basis,
                key="trailing_stop_candles_basis",
            )
            if trailing_stop_candles_basis == "distance":
                trailing_stop_distance = st.number_input(
                    "Distancia",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key="trailing_stop_distance",
                )
            else:
                trailing_stop_candle_count = st.number_input(
                    "Numero de candles",
                    min_value=1,
                    value=1,
                    step=1,
                    key="trailing_stop_candle_count",
                )
            trailing_stop_reference = st.selectbox(
                "Posicionar em",
                options=STOP_PRICE_REFERENCE_OPTIONS,
                key="trailing_stop_reference",
            )
        elif trailing_stop_type == "indicator":
            trailing_stop_indicator = st.selectbox(
                "Indicador",
                options=INITIAL_INDICATORS,
                key="trailing_stop_indicator",
            )

    return {
        "enabled": trailing_stop_enabled == "Sim",
        "calculation_type": trailing_stop_calculation_type,
        "type": trailing_stop_type,
        "acionar_a_favor": float(trailing_stop_acionar_a_favor),
        "passe": float(trailing_stop_passe),
        "candles_basis": trailing_stop_candles_basis,
        "distance": float(trailing_stop_distance),
        "candle_count": int(trailing_stop_candle_count),
        "reference": trailing_stop_reference,
        "indicator": trailing_stop_indicator,
    }


def render_saidas_parciais() -> dict:
    partial_exits_enabled = st.radio(
        "Usar saidas parciais?",
        options=YES_NO_OPTIONS,
        key="custom_partial_exits",
        horizontal=True,
    )
    partial_exits_calculation_type = STOP_TYPES[0]
    partial_exits_levels: list[dict[str, float]] = []

    if partial_exits_enabled == "Sim":
        partial_exits_calculation_type = st.selectbox(
            "Calculo",
            options=STOP_TYPES,
            format_func=_format_distance_type,
            key="partial_exits_calculation_type",
        )
        partial_exit_value_label = (
            "Pontos" if partial_exits_calculation_type == "points" else "% da posicao"
        )
        partial_exits_count = st.number_input(
            "Quantidade de saidas",
            min_value=1,
            max_value=3,
            value=1,
            step=1,
            key="partial_exits_count",
        )

        total_exit_percent = 0.0
        for level_index in range(int(partial_exits_count)):
            with st.expander(f"Saida parcial {level_index + 1}", expanded=level_index == 0):
                target_col, percent_col = st.columns(2)
                with target_col:
                    target_distance = st.number_input(
                        "Distancia alvo",
                        min_value=0.0,
                        value=float((level_index + 1) * 100),
                        step=1.0,
                        key=f"partial_exit_target_{level_index}",
                    )
                with percent_col:
                    exit_percent = st.number_input(
                        partial_exit_value_label,
                        min_value=0.0,
                        max_value=100.0,
                        value=50.0 if level_index == 0 else 25.0,
                        step=1.0,
                        key=f"partial_exit_percent_{level_index}",
                    )

                total_exit_percent += float(exit_percent)
                partial_exits_levels.append(
                    {
                        "target_distance": float(target_distance),
                        "exit_percent": float(exit_percent),
                    }
                )

        if total_exit_percent > 100:
            st.warning("A soma dos percentuais de saida parcial esta acima de 100%.")
        else:
            st.caption(f"Percentual total configurado: {total_exit_percent:.1f}%")

    return {
        "enabled": partial_exits_enabled == "Sim",
        "calculation_type": partial_exits_calculation_type,
        "levels": partial_exits_levels,
    }


def render_sinais_prontos() -> dict:
    signal_indicator_1 = READY_SIGNAL_INDICATOR_OPTIONS[0]
    band_channels_signal = "Nao usar"
    band_channels_enabled = False
    band_channels_indicator = BAND_CHANNEL_INDICATOR_OPTIONS[0]
    band_channels_period = 20
    band_channels_deviation = 2.0
    band_channels_signal_options = [
        "Fechou fora",
        "Fechou dentro e saiu",
        "Fechou dentro e fechou fora",
        "Fechou fora e voltou",
        "Fechou fora e fechou dentro",
        "Estando fora",
    ]

    crossover_enabled = False
    crossover_fast_indicator = CROSSOVER_INDICATOR_OPTIONS[0]
    crossover_fast_period = 9
    crossover_slow_indicator = CROSSOVER_INDICATOR_OPTIONS[1]
    crossover_slow_period = 21
    crossover_signal = "Cruzamento para compra"

    overbought_oversold_signal = "Nao usar"
    overbought_oversold_enabled = False
    overbought_oversold_indicator = OVERBOUGHT_OVERSOLD_INDICATOR_OPTIONS[0]
    overbought_oversold_period = 14
    overbought_level = 70
    oversold_level = 30

    with st.expander("Canais de bandas", expanded=False):
        band_channels_enabled = (
            st.radio(
                "Usar sinal de canais de bandas?",
                options=YES_NO_OPTIONS,
                key="ready_band_channels_enabled",
                horizontal=True,
            )
            == "Sim"
        )
        if band_channels_enabled:
            band_channels_signal = st.selectbox(
                "Sinais",
                options=band_channels_signal_options,
                key="ready_band_channels_signal_option",
            )
            indicator_col, period_col = st.columns(2)
            with indicator_col:
                band_channels_indicator = st.selectbox(
                    "Indicador",
                    options=BAND_CHANNEL_INDICATOR_OPTIONS,
                    key="ready_band_channels_indicator",
                )
            with period_col:
                band_channels_period = st.number_input(
                    "Periodo",
                    min_value=1,
                    value=20,
                    step=1,
                    key="ready_band_channels_period",
                )
            deviation_col, signal_col = st.columns(2)
            with deviation_col:
                band_channels_deviation = st.number_input(
                    "Desvio",
                    min_value=0.1,
                    value=2.0,
                    step=0.1,
                    key="ready_band_channels_deviation",
                )
            with signal_col:
                st.caption(f"Sinal selecionado: {band_channels_signal}")

    with st.expander("Cruzamentos", expanded=False):
        crossover_enabled = (
            st.radio(
                "Usar sinal de cruzamentos?",
                options=YES_NO_OPTIONS,
                key="ready_crossover_enabled",
                horizontal=True,
            )
            == "Sim"
        )
        if crossover_enabled:
            fast_indicator_col, fast_period_col = st.columns(2)
            with fast_indicator_col:
                crossover_fast_indicator = st.selectbox(
                    "Indicador rapido",
                    options=CROSSOVER_INDICATOR_OPTIONS,
                    key="ready_crossover_fast_indicator",
                )
            with fast_period_col:
                crossover_fast_period = st.number_input(
                    "Periodo rapido",
                    min_value=1,
                    value=9,
                    step=1,
                    key="ready_crossover_fast_period",
                )
            slow_indicator_col, slow_period_col = st.columns(2)
            with slow_indicator_col:
                crossover_slow_indicator = st.selectbox(
                    "Indicador lento",
                    options=CROSSOVER_INDICATOR_OPTIONS,
                    index=1,
                    key="ready_crossover_slow_indicator",
                )
            with slow_period_col:
                crossover_slow_period = st.number_input(
                    "Periodo lento",
                    min_value=1,
                    value=21,
                    step=1,
                    key="ready_crossover_slow_period",
                )
            crossover_signal = st.selectbox(
                "Sinal",
                options=[
                    "Cruzamento para compra",
                    "Cruzamento para venda",
                    "Ambos",
                ],
                key="ready_crossover_signal",
            )

    with st.expander("Sobre comprado/vendido", expanded=False):
        overbought_oversold_signal = st.selectbox(
            "Condicao",
            options=[
                "Nao usar",
                "Fechou fora",
                "Fechou dentro e saiu",
                "Fechou dentro e fechou fora",
                "Fechou fora e voltou",
                "Fechou fora e fechou dentro",
                "Estando fora",
            ],
            key="ready_overbought_oversold_signal",
        )
        overbought_oversold_enabled = overbought_oversold_signal != "Nao usar"
        if overbought_oversold_enabled:
            indicator_col, period_col = st.columns(2)
            with indicator_col:
                overbought_oversold_indicator = st.selectbox(
                    "Indicador",
                    options=OVERBOUGHT_OVERSOLD_INDICATOR_OPTIONS,
                    key="ready_overbought_oversold_indicator",
                )
            with period_col:
                overbought_oversold_period = st.number_input(
                    "Periodo",
                    min_value=1,
                    value=14,
                    step=1,
                    key="ready_overbought_oversold_period",
                )
            overbought_col, oversold_col = st.columns(2)
            with overbought_col:
                overbought_level = st.number_input(
                    "Nivel de sobrecompra",
                    min_value=0,
                    max_value=100,
                    value=70,
                    step=1,
                    key="ready_overbought_level",
                )
            with oversold_col:
                oversold_level = st.number_input(
                    "Nivel de sobrevenda",
                    min_value=0,
                    max_value=100,
                    value=30,
                    step=1,
                    key="ready_oversold_level",
                )
            st.caption(f"Condicao selecionada: {overbought_oversold_signal}")

    with st.expander("Configurar sinais", expanded=False):
        signal_indicator_1 = st.selectbox(
            "Indicador 1",
            options=READY_SIGNAL_INDICATOR_OPTIONS,
            key="ready_signal_indicator_1",
        )

    return {
        "signal_settings": {
            "indicator_1": signal_indicator_1,
        },
        "band_channels": {
            "enabled": band_channels_enabled,
            "indicator": band_channels_indicator,
            "period": int(band_channels_period),
            "deviation": float(band_channels_deviation),
            "signal": band_channels_signal,
        },
        "crossovers": {
            "enabled": crossover_enabled,
            "fast_indicator": crossover_fast_indicator,
            "fast_period": int(crossover_fast_period),
            "slow_indicator": crossover_slow_indicator,
            "slow_period": int(crossover_slow_period),
            "signal": crossover_signal,
        },
        "overbought_oversold": {
            "enabled": overbought_oversold_enabled,
            "indicator": overbought_oversold_indicator,
            "period": int(overbought_oversold_period),
            "overbought_level": int(overbought_level),
            "oversold_level": int(oversold_level),
            "signal": overbought_oversold_signal,
        },
    }
