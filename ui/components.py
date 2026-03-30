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
MA_TYPE_OPTIONS = [
    "Simples (SMA)",
    "Exponencial (EMA)",
    "Suavizada (SMMA)",
    "Linear-ponderada (LWMA)",
]
PRICE_MODE_OPTIONS = [
    "Fechamento",
    "Abertura",
    "Maximo",
    "Minimo",
    "Mediano",
    "Tipico",
    "Medio",
]
VOLUME_TYPE_OPTIONS = [
    "Volume de tick",
    "Volume Real",
]
STOCHASTIC_TYPE_OPTIONS = [
    "Minimo/Maximo",
    "Fechamento/Fechamento",
]
SIGNAL_RULE_COUNT = 5
FINAL_ADJUSTMENT_FIELDS = [
    (
        "cancel_pending_on_opposite_signal",
        "Cancelar pendente de entrada se aparecer sinal oposto",
        "Sim",
    ),
    (
        "reposition_stop_loss_on_favorable_move",
        "Reposicionar stoploss no aumento a favor da operacao",
        "Sim",
    ),
    (
        "reposition_take_profit_on_adverse_move",
        "Reposicionar takeprofit no aumento contra a operacao",
        "Sim",
    ),
    (
        "move_stop_loss_based_on_average_price",
        "Movimentar stoploss com base no preco medio",
        "Sim",
    ),
    (
        "move_take_profit_based_on_average_price",
        "Movimentar takeprofit com base no preco medio",
        "Sim",
    ),
    (
        "use_average_price_for_partial_exits",
        "Usar preco medio como referencia das parciais",
        "Sim",
    ),
    (
        "block_exit_signal_on_entry_candle",
        "Impedir sinal de saida na vela que gerou entrada",
        "Sim",
    ),
    (
        "block_entry_signal_on_exit_candle",
        "Impedir sinal de entrada na vela que gerou saida",
        "Sim",
    ),
    (
        "recalculate_average_price_from_partial_exits",
        "Recalcular o preco medio com base nas saidas parciais",
        "Nao",
    ),
]
SIGNAL_LOGICAL_COMMAND_OPTIONS = [
    "SE",
    "E",
    "OU",
    "E SE",
    "OU SE",
    "E Tambem",
    "OU Tambem",
]
SIGNAL_RULE_OPERATOR_LABELS = {
    "GREATER_THAN": "Maior que",
    "LESS_THAN": "Menor que",
    "GREATER_OR_EQUAL": "Maior ou igual que",
    "LESS_OR_EQUAL": "Menor ou igual que",
    "EQUAL": "Igual que",
    "NOT_EQUAL": "Diferente de",
    "CROSS_UP": "Cruzar p/ cima de",
    "CROSS_DOWN": "Cruzar p/ baixo de",
    "CROSS_AND_CLOSE_ABOVE": "Cruzar & fechar acima de",
    "CROSS_AND_CLOSE_BELOW": "Cruzar & fechar abaixo de",
}
SIGNAL_RULE_CANDLE_LABELS = {
    0: "Vela atual (0)",
    1: "Vela anterior (1)",
    2: "Penultima vela (2)",
    3: "Anti Penultima (3)",
}
SIGNAL_RULE_SOURCE_LABELS = {
    "NONE": "Nao usar",
    "ABSOLUTE_VALUE": "Valor absoluto",
    "POINT_VALUE": "Valor em pontos",
    "ENTRY_PRICE": "Preco de entrada",
    "AVERAGE_PRICE": "Preco Medio",
    "CURRENT_PRICE": "Preco Atual",
    "CANDLE_CLOSE": "Fechamento da vela",
    "CANDLE_OPEN": "Abertura da vela",
    "CANDLE_HIGH": "Maxima da vela",
    "CANDLE_LOW": "Minima da vela",
    "DAY_CLOSE": "Fechamento do dia",
    "DAY_OPEN": "Abertura do dia",
    "DAY_HIGH": "Maxima do dia",
    "DAY_LOW": "Minima do dia",
    "CANDLE_SIZE": "Tamanho da vela",
    "CANDLE_BODY": "Corpo da vela",
    "EMPTY_VALUE": "Empty Value",
}
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

SIGNAL_INDICATOR_OUTPUT_LABELS = {
    "Keltner": ["Superior", "Media", "Inferior"],
    "Donchian": ["Superior", "Meio", "Inferior"],
    "Regressao": ["Valor"],
    "Afastamento da media": ["Valor"],
    "Desvio Medio": ["Valor"],
    "Canal ATR": ["Superior", "Media", "Inferior"],
    "Media Movel": ["Valor"],
    "Bandas de Bollinger": ["Superior", "Media", "Inferior"],
    "MACD": ["Linha MACD", "Linha de sinal", "Histograma"],
    "Envelopes": ["Superior", "Media", "Inferior"],
    "Estocastico": ["%K", "%D"],
    "RSI (Relative Strength Index)": ["Valor"],
    "Desvio Padrao": ["Valor"],
    "Volume": ["Valor"],
    "ATR (Average True Range)": ["Valor"],
    "Parabolic SAR": ["Valor"],
    "Fractal": ["Superior", "Inferior"],
    "OBV (On Balance Volume)": ["Valor"],
    "Acumulacao/Distribuicao (A/D)": ["Valor"],
    "MFI (Money Flow Index)": ["Valor"],
    "Vidya": ["Valor"],
    "DEMA": ["Valor"],
    "TEMA": ["Valor"],
    "FRAMA": ["Valor"],
    "TRIX": ["Valor"],
    "Bears Power": ["Valor"],
    "Bulls Power": ["Valor"],
    "Chaikin Oscilador": ["Valor"],
    "Accelerator Oscillator": ["Valor"],
    "Awesome Oscillator": ["Valor"],
    "CCI (Commodity Channel Index)": ["Valor"],
    "DeMarker": ["Valor"],
    "Alligator": ["Mandibula", "Dente", "Boca"],
    "Nuvem de Ichimoku": [
        "Tenkan-sen",
        "Kijun-sen",
        "Senkou Span A",
        "Senkou Span B",
        "Chikou Span",
    ],
    "ADX (Average Directional Index)": ["ADX", "+DI", "-DI"],
    "ADX Welles Wilder": ["ADX", "+DI", "-DI"],
    "Gator Oscillator": ["Superior", "Inferior"],
    "Williams %R (WPR)": ["Valor"],
    "Market Facilitation Index": ["Valor"],
    "Momentum": ["Valor"],
    "RVI (Relative Vigor Index)": ["RVI", "Sinal"],
}


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


def _build_signal_rule_source_options(
    indicators: list[str],
) -> tuple[list[str], dict[str, str]]:
    options = list(SIGNAL_RULE_SOURCE_LABELS.keys())
    labels = dict(SIGNAL_RULE_SOURCE_LABELS)

    for indicator_index, indicator_name in enumerate(indicators, start=1):
        if indicator_name in {"Nao usar", "Externo"}:
            continue

        output_labels = SIGNAL_INDICATOR_OUTPUT_LABELS.get(indicator_name, ["Valor"])
        for output_label in output_labels:
            option_value = f"INDICATOR_{indicator_index}:{output_label}"
            option_label = f"Indicador {indicator_index} - {indicator_name} - {output_label}"
            options.append(option_value)
            labels[option_value] = option_label

    return options, labels


def _render_signal_rule_row(
    rule_index: int,
    source_options: list[str],
    source_labels: dict[str, str],
) -> dict:
    logical_command_key = f"ready_signal_rule_{rule_index}_logical_command"
    source_a_key = f"ready_signal_rule_{rule_index}_source_a"
    candle_a_key = f"ready_signal_rule_{rule_index}_candle_a"
    operator_key = f"ready_signal_rule_{rule_index}_operator"
    source_b_key = f"ready_signal_rule_{rule_index}_source_b"
    candle_b_key = f"ready_signal_rule_{rule_index}_candle_b"

    if st.session_state.get(logical_command_key) not in SIGNAL_LOGICAL_COMMAND_OPTIONS:
        st.session_state[logical_command_key] = SIGNAL_LOGICAL_COMMAND_OPTIONS[0]
    if st.session_state.get(source_a_key) not in source_options:
        st.session_state[source_a_key] = source_options[0]
    if st.session_state.get(candle_a_key) not in SIGNAL_RULE_CANDLE_LABELS:
        st.session_state[candle_a_key] = 0
    if st.session_state.get(operator_key) not in SIGNAL_RULE_OPERATOR_LABELS:
        st.session_state[operator_key] = list(SIGNAL_RULE_OPERATOR_LABELS.keys())[0]
    if st.session_state.get(source_b_key) not in source_options:
        st.session_state[source_b_key] = source_options[0]
    if st.session_state.get(candle_b_key) not in SIGNAL_RULE_CANDLE_LABELS:
        st.session_state[candle_b_key] = 0

    command_col, source_a_col, candle_a_col, operator_col, source_b_col, candle_b_col = st.columns(
        [1.35, 2.35, 1.6, 2.1, 2.35, 1.6]
    )

    with command_col:
        logical_command = st.selectbox(
            f"Comando logico {rule_index + 1}",
            options=SIGNAL_LOGICAL_COMMAND_OPTIONS,
            key=logical_command_key,
            label_visibility="collapsed",
        )
    with source_a_col:
        source_a = st.selectbox(
            f"Fonte A {rule_index + 1}",
            options=source_options,
            format_func=lambda value: source_labels[value],
            key=source_a_key,
            label_visibility="collapsed",
        )
    with candle_a_col:
        candle_a = st.selectbox(
            f"Candle A {rule_index + 1}",
            options=list(SIGNAL_RULE_CANDLE_LABELS.keys()),
            format_func=lambda value: SIGNAL_RULE_CANDLE_LABELS[value],
            key=candle_a_key,
            label_visibility="collapsed",
        )
    with operator_col:
        operator = st.selectbox(
            f"Operador {rule_index + 1}",
            options=list(SIGNAL_RULE_OPERATOR_LABELS.keys()),
            format_func=lambda value: SIGNAL_RULE_OPERATOR_LABELS[value],
            key=operator_key,
            label_visibility="collapsed",
        )
    with source_b_col:
        source_b = st.selectbox(
            f"Fonte B {rule_index + 1}",
            options=source_options,
            format_func=lambda value: source_labels[value],
            key=source_b_key,
            label_visibility="collapsed",
        )
    with candle_b_col:
        candle_b = st.selectbox(
            f"Candle B {rule_index + 1}",
            options=list(SIGNAL_RULE_CANDLE_LABELS.keys()),
            format_func=lambda value: SIGNAL_RULE_CANDLE_LABELS[value],
            key=candle_b_key,
            label_visibility="collapsed",
        )

    return {
        "logical_command": logical_command,
        "source_a": {
            "value": source_a,
            "label": source_labels[source_a],
        },
        "candle_a": {
            "value": int(candle_a),
            "label": SIGNAL_RULE_CANDLE_LABELS[candle_a],
        },
        "operator": {
            "value": operator,
            "label": SIGNAL_RULE_OPERATOR_LABELS[operator],
        },
        "source_b": {
            "value": source_b,
            "label": source_labels[source_b],
        },
        "candle_b": {
            "value": int(candle_b),
            "label": SIGNAL_RULE_CANDLE_LABELS[candle_b],
        },
    }


def _build_signal_indicator_summary(selected_indicator: str) -> str:
    if selected_indicator == "Nao usar":
        return "Slot livre para composicao da regra."
    if selected_indicator == "Externo":
        return "Reservado para integracao externa."

    outputs = SIGNAL_INDICATOR_OUTPUT_LABELS.get(selected_indicator, ["Valor"])
    if len(outputs) == 1:
        return f"Saida principal: {outputs[0]}"

    return f"Saidas: {', '.join(outputs[:3])}"


def _render_signal_indicator_card(
    slot_number: int,
) -> tuple[str, dict]:
    indicator_key = f"ready_signal_indicator_{slot_number}"
    selected_indicator = st.session_state.get(
        indicator_key,
        READY_SIGNAL_INDICATOR_OPTIONS[0],
    )
    parameters: dict = {}

    with st.expander(f"Indicador {slot_number}", expanded=selected_indicator != "Nao usar"):
        selected_indicator = st.selectbox(
            f"Indicador {slot_number}",
            options=READY_SIGNAL_INDICATOR_OPTIONS,
            key=indicator_key,
            label_visibility="collapsed",
        )
        st.markdown(
            (
                "<div class='signal-card-meta'>"
                f"<span class='signal-card-badge'>{selected_indicator}</span>"
                f"<span class='signal-card-summary'>{_build_signal_indicator_summary(selected_indicator)}</span>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        parameters = _render_signal_indicator_parameters(slot_number, selected_indicator)

    return selected_indicator, parameters


def _signal_indicator_key(slot_number: int, suffix: str) -> str:
    return f"ready_signal_indicator_{slot_number}_{suffix}"


def _render_signal_indicator_parameters(slot_number: int, selected_indicator: str) -> dict:
    if selected_indicator == "Keltner":
        period_col, ma_type_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=2,
                step=1,
                key=_signal_indicator_key(slot_number, "keltner_period"),
            )
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "keltner_ma_type"),
            )
        deviation = st.text_input(
            "Desvios",
            value="",
            key=_signal_indicator_key(slot_number, "keltner_deviation"),
        )
        return {
            "period": int(period),
            "deviation": deviation,
            "ma_type": ma_type,
        }

    if selected_indicator == "Donchian":
        period = st.number_input(
            "Periodo",
            min_value=1,
            value=21,
            step=1,
            key=_signal_indicator_key(slot_number, "donchian_period"),
        )
        return {
            "period": int(period),
        }

    if selected_indicator == "Regressao":
        period_col, ma_type_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=18,
                step=1,
                key=_signal_indicator_key(slot_number, "regression_period"),
            )
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "regression_ma_type"),
            )
        price_mode = st.selectbox(
            "Modo de preco",
            options=PRICE_MODE_OPTIONS,
            key=_signal_indicator_key(slot_number, "regression_price_mode"),
        )
        return {
            "period": int(period),
            "ma_type": ma_type,
            "price_mode": price_mode,
        }

    if selected_indicator == "Afastamento da media":
        period_col, displacement_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "deviation_period"),
            )
        with displacement_col:
            displacement = st.number_input(
                "Deslocamento",
                value=0,
                step=1,
                key=_signal_indicator_key(slot_number, "deviation_shift"),
            )
        ma_type_col, price_mode_col = st.columns(2)
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "deviation_ma_type"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "deviation_price_mode"),
            )
        return {
            "period": int(period),
            "displacement": int(displacement),
            "ma_type": ma_type,
            "price_mode": price_mode,
        }

    if selected_indicator == "Desvio Medio":
        period_col, ma_type_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=2,
                step=1,
                key=_signal_indicator_key(slot_number, "mean_deviation_period"),
            )
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "mean_deviation_ma_type"),
            )
        price_mode = st.selectbox(
            "Modo de preco",
            options=PRICE_MODE_OPTIONS,
            index=None,
            placeholder="Selecione",
            key=_signal_indicator_key(slot_number, "mean_deviation_price_mode"),
        )
        return {
            "period": int(period),
            "ma_type": ma_type,
            "price_mode": price_mode,
        }

    if selected_indicator == "Canal ATR":
        period_col, deviation_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "atr_channel_period"),
            )
        with deviation_col:
            deviation = st.number_input(
                "Desvios",
                min_value=0.0,
                value=2.0,
                step=0.1,
                key=_signal_indicator_key(slot_number, "atr_channel_deviation"),
            )
        return {
            "period": int(period),
            "deviation": float(deviation),
        }

    if selected_indicator == "Media Movel":
        period_col, displacement_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=21,
                step=1,
                key=_signal_indicator_key(slot_number, "moving_average_period"),
            )
        with displacement_col:
            displacement = st.number_input(
                "Deslocamento",
                value=0,
                step=1,
                key=_signal_indicator_key(slot_number, "moving_average_shift"),
            )
        ma_type_col, price_mode_col = st.columns(2)
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "moving_average_ma_type"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "moving_average_price_mode"),
            )
        return {
            "period": int(period),
            "displacement": int(displacement),
            "ma_type": ma_type,
            "price_mode": price_mode,
        }

    if selected_indicator == "Bandas de Bollinger":
        period_col, deviation_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=20,
                step=1,
                key=_signal_indicator_key(slot_number, "bollinger_period"),
            )
        with deviation_col:
            deviation = st.number_input(
                "Desvios",
                min_value=0.0,
                value=2.0,
                step=0.1,
                key=_signal_indicator_key(slot_number, "bollinger_deviation"),
            )
        displacement_col, price_mode_col = st.columns(2)
        with displacement_col:
            displacement = st.number_input(
                "Deslocamento",
                value=0,
                step=1,
                key=_signal_indicator_key(slot_number, "bollinger_shift"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "bollinger_price_mode"),
            )
        return {
            "period": int(period),
            "deviation": float(deviation),
            "displacement": int(displacement),
            "price_mode": price_mode,
        }

    if selected_indicator == "MACD":
        fast_ema_col, slow_ema_col = st.columns(2)
        with fast_ema_col:
            fast_ema = st.number_input(
                "EMA rapida",
                min_value=1,
                value=2,
                step=1,
                key=_signal_indicator_key(slot_number, "macd_fast_ema"),
            )
        with slow_ema_col:
            slow_ema = st.text_input(
                "EMA lenta",
                value="",
                key=_signal_indicator_key(slot_number, "macd_slow_ema"),
            )
        signal_col, price_mode_col = st.columns(2)
        with signal_col:
            signal = st.text_input(
                "Sinal",
                value="",
                key=_signal_indicator_key(slot_number, "macd_signal"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "macd_price_mode"),
            )
        return {
            "fast_ema": int(fast_ema),
            "slow_ema": slow_ema,
            "signal": signal,
            "price_mode": price_mode,
        }

    if selected_indicator == "Envelopes":
        period_col, displacement_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "envelopes_period"),
            )
        with displacement_col:
            displacement = st.number_input(
                "Deslocamento",
                value=0,
                step=1,
                key=_signal_indicator_key(slot_number, "envelopes_shift"),
            )
        ma_type_col, price_mode_col = st.columns(2)
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "envelopes_ma_type"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "envelopes_price_mode"),
            )
        deviation = st.number_input(
            "Desvios",
            min_value=0.0,
            value=1.0,
            step=0.1,
            key=_signal_indicator_key(slot_number, "envelopes_deviation"),
        )
        return {
            "period": int(period),
            "displacement": int(displacement),
            "ma_type": ma_type,
            "price_mode": price_mode,
            "deviation": float(deviation),
        }

    if selected_indicator == "Estocastico":
        k_period_col, d_period_col = st.columns(2)
        with k_period_col:
            k_period = st.number_input(
                "K Periodo",
                min_value=1,
                value=5,
                step=1,
                key=_signal_indicator_key(slot_number, "stochastic_k_period"),
            )
        with d_period_col:
            d_period = st.number_input(
                "D Periodo",
                min_value=1,
                value=3,
                step=1,
                key=_signal_indicator_key(slot_number, "stochastic_d_period"),
            )
        slowing_col, ma_type_col = st.columns(2)
        with slowing_col:
            slowing = st.number_input(
                "Lentidao",
                min_value=1,
                value=3,
                step=1,
                key=_signal_indicator_key(slot_number, "stochastic_slowing"),
            )
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "stochastic_ma_type"),
            )
        stochastic_type = st.selectbox(
            "Tipo estocastico",
            options=STOCHASTIC_TYPE_OPTIONS,
            key=_signal_indicator_key(slot_number, "stochastic_type"),
        )
        return {
            "k_period": int(k_period),
            "d_period": int(d_period),
            "slowing": int(slowing),
            "ma_type": ma_type,
            "stochastic_type": stochastic_type,
        }

    if selected_indicator == "RSI (Relative Strength Index)":
        period_col, price_mode_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "rsi_period"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "rsi_price_mode"),
            )
        return {
            "period": int(period),
            "price_mode": price_mode,
        }

    if selected_indicator == "Desvio Padrao":
        period_col, displacement_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=2,
                step=1,
                key=_signal_indicator_key(slot_number, "stddev_period"),
            )
        with displacement_col:
            displacement = st.text_input(
                "Deslocamento",
                value="",
                key=_signal_indicator_key(slot_number, "stddev_shift"),
            )
        ma_type_col, price_mode_col = st.columns(2)
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "stddev_ma_type"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "stddev_price_mode"),
            )
        return {
            "period": int(period),
            "displacement": displacement,
            "ma_type": ma_type,
            "price_mode": price_mode,
        }

    if selected_indicator == "Volume":
        volume_type = st.selectbox(
            "Tipo",
            options=VOLUME_TYPE_OPTIONS,
            key=_signal_indicator_key(slot_number, "volume_type"),
        )
        return {
            "type": volume_type,
        }

    if selected_indicator == "ATR (Average True Range)":
        period = st.number_input(
            "Periodo",
            min_value=1,
            value=14,
            step=1,
            key=_signal_indicator_key(slot_number, "atr_period"),
        )
        return {
            "period": int(period),
        }

    if selected_indicator == "Parabolic SAR":
        step_col, maximum_col = st.columns(2)
        with step_col:
            step_value = st.number_input(
                "Passo",
                min_value=0.0,
                value=0.02,
                step=0.01,
                format="%.2f",
                key=_signal_indicator_key(slot_number, "parabolic_sar_step"),
            )
        with maximum_col:
            maximum_value = st.number_input(
                "Maximo",
                min_value=0.0,
                value=0.2,
                step=0.1,
                format="%.1f",
                key=_signal_indicator_key(slot_number, "parabolic_sar_maximum"),
            )
        return {
            "step": float(step_value),
            "maximum": float(maximum_value),
        }

    if selected_indicator == "Fractal":
        st.caption("Fractal nao requer parametros.")
        return {}

    if selected_indicator == "OBV (On Balance Volume)":
        volume_type = st.selectbox(
            "Volume",
            options=VOLUME_TYPE_OPTIONS,
            key=_signal_indicator_key(slot_number, "obv_volume_type"),
        )
        return {
            "volume_type": volume_type,
        }

    if selected_indicator == "Acumulacao/Distribuicao (A/D)":
        volume_type = st.selectbox(
            "Volume",
            options=VOLUME_TYPE_OPTIONS,
            key=_signal_indicator_key(slot_number, "ad_volume_type"),
        )
        return {
            "volume_type": volume_type,
        }

    if selected_indicator == "MFI (Money Flow Index)":
        period_col, volume_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "mfi_period"),
            )
        with volume_col:
            volume_type = st.selectbox(
                "Volume",
                options=VOLUME_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "mfi_volume_type"),
            )
        return {
            "period": int(period),
            "volume_type": volume_type,
        }

    if selected_indicator == "Vidya":
        cmo_period_col, ema_period_col = st.columns(2)
        with cmo_period_col:
            cmo_period = st.number_input(
                "Periodo CMO",
                min_value=1,
                value=9,
                step=1,
                key=_signal_indicator_key(slot_number, "vidya_cmo_period"),
            )
        with ema_period_col:
            ema_period = st.number_input(
                "Periodo EMA",
                min_value=1,
                value=12,
                step=1,
                key=_signal_indicator_key(slot_number, "vidya_ema_period"),
            )
        displacement_col, price_mode_col = st.columns(2)
        with displacement_col:
            displacement = st.number_input(
                "Deslocamento",
                value=0,
                step=1,
                key=_signal_indicator_key(slot_number, "vidya_shift"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "vidya_price_mode"),
            )
        return {
            "cmo_period": int(cmo_period),
            "ema_period": int(ema_period),
            "displacement": int(displacement),
            "price_mode": price_mode,
        }

    if selected_indicator == "DEMA":
        period_col, displacement_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "dema_period"),
            )
        with displacement_col:
            displacement = st.number_input(
                "Deslocamento",
                value=0,
                step=1,
                key=_signal_indicator_key(slot_number, "dema_shift"),
            )
        price_mode = st.selectbox(
            "Modo de preco",
            options=PRICE_MODE_OPTIONS,
            key=_signal_indicator_key(slot_number, "dema_price_mode"),
        )
        return {
            "period": int(period),
            "displacement": int(displacement),
            "price_mode": price_mode,
        }

    if selected_indicator == "TEMA":
        period_col, displacement_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "tema_period"),
            )
        with displacement_col:
            displacement = st.number_input(
                "Deslocamento",
                value=0,
                step=1,
                key=_signal_indicator_key(slot_number, "tema_shift"),
            )
        price_mode = st.selectbox(
            "Modo de preco",
            options=PRICE_MODE_OPTIONS,
            key=_signal_indicator_key(slot_number, "tema_price_mode"),
        )
        return {
            "period": int(period),
            "displacement": int(displacement),
            "price_mode": price_mode,
        }

    if selected_indicator == "FRAMA":
        period_col, displacement_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "frama_period"),
            )
        with displacement_col:
            displacement = st.number_input(
                "Deslocamento",
                value=0,
                step=1,
                key=_signal_indicator_key(slot_number, "frama_shift"),
            )
        price_mode = st.selectbox(
            "Modo de preco",
            options=PRICE_MODE_OPTIONS,
            key=_signal_indicator_key(slot_number, "frama_price_mode"),
        )
        return {
            "period": int(period),
            "displacement": int(displacement),
            "price_mode": price_mode,
        }

    if selected_indicator == "TRIX":
        period_col, price_mode_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "trix_period"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "trix_price_mode"),
            )
        return {
            "period": int(period),
            "price_mode": price_mode,
        }

    if selected_indicator == "Bears Power":
        period = st.number_input(
            "Periodo",
            min_value=1,
            value=13,
            step=1,
            key=_signal_indicator_key(slot_number, "bears_power_period"),
        )
        return {
            "period": int(period),
        }

    if selected_indicator == "Bulls Power":
        period = st.number_input(
            "Periodo",
            min_value=1,
            value=13,
            step=1,
            key=_signal_indicator_key(slot_number, "bulls_power_period"),
        )
        return {
            "period": int(period),
        }

    if selected_indicator == "Chaikin Oscilador":
        fast_ma_col, slow_ma_col = st.columns(2)
        with fast_ma_col:
            fast_ma = st.number_input(
                "Media rapida",
                min_value=1,
                value=3,
                step=1,
                key=_signal_indicator_key(slot_number, "chaikin_fast_ma"),
            )
        with slow_ma_col:
            slow_ma = st.number_input(
                "Media lenta",
                min_value=1,
                value=10,
                step=1,
                key=_signal_indicator_key(slot_number, "chaikin_slow_ma"),
            )
        ma_type_col, volume_type_col = st.columns(2)
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "chaikin_ma_type"),
            )
        with volume_type_col:
            volume_type = st.selectbox(
                "Volume",
                options=VOLUME_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "chaikin_volume_type"),
            )
        return {
            "fast_ma": int(fast_ma),
            "slow_ma": int(slow_ma),
            "ma_type": ma_type,
            "volume_type": volume_type,
        }

    if selected_indicator == "Accelerator Oscillator":
        st.caption("Accelerator Oscillator nao requer parametros.")
        return {}

    if selected_indicator == "Awesome Oscillator":
        st.caption("Awesome Oscillator nao requer parametros.")
        return {}

    if selected_indicator == "CCI (Commodity Channel Index)":
        period_col, price_mode_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "cci_period"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "cci_price_mode"),
            )
        return {
            "period": int(period),
            "price_mode": price_mode,
        }

    if selected_indicator == "DeMarker":
        period = st.number_input(
            "Periodo",
            min_value=1,
            value=14,
            step=1,
            key=_signal_indicator_key(slot_number, "demarker_period"),
        )
        return {
            "period": int(period),
        }

    if selected_indicator == "Alligator":
        jaw_period_col, jaw_shift_col = st.columns(2)
        with jaw_period_col:
            jaw_period = st.number_input(
                "Periodo mandibula",
                min_value=1,
                value=13,
                step=1,
                key=_signal_indicator_key(slot_number, "alligator_jaw_period"),
            )
        with jaw_shift_col:
            jaw_shift = st.number_input(
                "Deslocamento mandibula",
                value=8,
                step=1,
                key=_signal_indicator_key(slot_number, "alligator_jaw_shift"),
            )
        teeth_period_col, teeth_shift_col = st.columns(2)
        with teeth_period_col:
            teeth_period = st.number_input(
                "Periodo dente",
                min_value=1,
                value=8,
                step=1,
                key=_signal_indicator_key(slot_number, "alligator_teeth_period"),
            )
        with teeth_shift_col:
            teeth_shift = st.number_input(
                "Deslocamento dente",
                value=5,
                step=1,
                key=_signal_indicator_key(slot_number, "alligator_teeth_shift"),
            )
        lips_period_col, lips_shift_col = st.columns(2)
        with lips_period_col:
            lips_period = st.number_input(
                "Periodo boca",
                min_value=1,
                value=5,
                step=1,
                key=_signal_indicator_key(slot_number, "alligator_lips_period"),
            )
        with lips_shift_col:
            lips_shift = st.number_input(
                "Deslocamento boca",
                value=3,
                step=1,
                key=_signal_indicator_key(slot_number, "alligator_lips_shift"),
            )
        ma_type_col, price_mode_col = st.columns(2)
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "alligator_ma_type"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "alligator_price_mode"),
            )
        return {
            "jaw_period": int(jaw_period),
            "jaw_shift": int(jaw_shift),
            "teeth_period": int(teeth_period),
            "teeth_shift": int(teeth_shift),
            "lips_period": int(lips_period),
            "lips_shift": int(lips_shift),
            "ma_type": ma_type,
            "price_mode": price_mode,
        }

    if selected_indicator == "Nuvem de Ichimoku":
        tenkan_col, kijun_col = st.columns(2)
        with tenkan_col:
            tenkan_sen = st.number_input(
                "Tenkan-sen",
                min_value=1,
                value=9,
                step=1,
                key=_signal_indicator_key(slot_number, "ichimoku_tenkan_sen"),
            )
        with kijun_col:
            kijun_sen = st.number_input(
                "Kijun-sen",
                min_value=1,
                value=26,
                step=1,
                key=_signal_indicator_key(slot_number, "ichimoku_kijun_sen"),
            )
        senkou_span_b = st.number_input(
            "Senkou Span B",
            min_value=1,
            value=52,
            step=1,
            key=_signal_indicator_key(slot_number, "ichimoku_senkou_span_b"),
        )
        return {
            "tenkan_sen": int(tenkan_sen),
            "kijun_sen": int(kijun_sen),
            "senkou_span_b": int(senkou_span_b),
        }

    if selected_indicator == "ADX (Average Directional Index)":
        period = st.number_input(
            "Periodo",
            min_value=1,
            value=14,
            step=1,
            key=_signal_indicator_key(slot_number, "adx_period"),
        )
        return {
            "period": int(period),
        }

    if selected_indicator == "ADX Welles Wilder":
        period = st.number_input(
            "Periodo",
            min_value=1,
            value=14,
            step=1,
            key=_signal_indicator_key(slot_number, "adx_wilder_period"),
        )
        return {
            "period": int(period),
        }

    if selected_indicator == "Gator Oscillator":
        jaw_period_col, jaw_shift_col = st.columns(2)
        with jaw_period_col:
            jaw_period = st.number_input(
                "Periodo mandibula",
                min_value=1,
                value=13,
                step=1,
                key=_signal_indicator_key(slot_number, "gator_jaw_period"),
            )
        with jaw_shift_col:
            jaw_shift = st.number_input(
                "Deslocamento mandibula",
                value=8,
                step=1,
                key=_signal_indicator_key(slot_number, "gator_jaw_shift"),
            )
        teeth_period_col, teeth_shift_col = st.columns(2)
        with teeth_period_col:
            teeth_period = st.number_input(
                "Periodo dente",
                min_value=1,
                value=8,
                step=1,
                key=_signal_indicator_key(slot_number, "gator_teeth_period"),
            )
        with teeth_shift_col:
            teeth_shift = st.number_input(
                "Deslocamento dente",
                value=5,
                step=1,
                key=_signal_indicator_key(slot_number, "gator_teeth_shift"),
            )
        lips_period_col, lips_shift_col = st.columns(2)
        with lips_period_col:
            lips_period = st.number_input(
                "Periodo boca",
                min_value=1,
                value=5,
                step=1,
                key=_signal_indicator_key(slot_number, "gator_lips_period"),
            )
        with lips_shift_col:
            lips_shift = st.number_input(
                "Deslocamento boca",
                value=3,
                step=1,
                key=_signal_indicator_key(slot_number, "gator_lips_shift"),
            )
        ma_type_col, price_mode_col = st.columns(2)
        with ma_type_col:
            ma_type = st.selectbox(
                "Tipo de media",
                options=MA_TYPE_OPTIONS,
                key=_signal_indicator_key(slot_number, "gator_ma_type"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "gator_price_mode"),
            )
        return {
            "jaw_period": int(jaw_period),
            "jaw_shift": int(jaw_shift),
            "teeth_period": int(teeth_period),
            "teeth_shift": int(teeth_shift),
            "lips_period": int(lips_period),
            "lips_shift": int(lips_shift),
            "ma_type": ma_type,
            "price_mode": price_mode,
        }

    if selected_indicator == "Williams %R (WPR)":
        period_col, deviation_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "wpr_period"),
            )
        with deviation_col:
            deviation = st.number_input(
                "Desvios",
                min_value=0.0,
                value=2.0,
                step=0.1,
                key=_signal_indicator_key(slot_number, "wpr_deviation"),
            )
        return {
            "period": int(period),
            "deviation": float(deviation),
        }

    if selected_indicator == "Market Facilitation Index":
        volume_type = st.selectbox(
            "Volume",
            options=VOLUME_TYPE_OPTIONS,
            key=_signal_indicator_key(slot_number, "market_facilitation_volume_type"),
        )
        return {
            "volume_type": volume_type,
        }

    if selected_indicator == "Momentum":
        period_col, price_mode_col = st.columns(2)
        with period_col:
            period = st.number_input(
                "Periodo medio",
                min_value=1,
                value=14,
                step=1,
                key=_signal_indicator_key(slot_number, "momentum_period"),
            )
        with price_mode_col:
            price_mode = st.selectbox(
                "Modo de preco",
                options=PRICE_MODE_OPTIONS,
                key=_signal_indicator_key(slot_number, "momentum_price_mode"),
            )
        return {
            "period": int(period),
            "price_mode": price_mode,
        }

    if selected_indicator == "RVI (Relative Vigor Index)":
        period = st.number_input(
            "Periodo",
            min_value=1,
            value=14,
            step=1,
            key=_signal_indicator_key(slot_number, "rvi_period"),
        )
        return {
            "period": int(period),
        }

    return {}


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


def render_ajustes_finais() -> dict:
    st.caption("Selecione algumas confirmacoes para os ajustes finais da estrategia.")

    final_adjustments: dict[str, bool] = {}
    with st.container(border=True):
        for field_key, label, default_value in FINAL_ADJUSTMENT_FIELDS:
            state_key = f"final_adjustment_{field_key}"
            current_value = st.session_state.get(state_key)
            if current_value not in YES_NO_OPTIONS:
                st.session_state[state_key] = default_value

            description_col, value_col = st.columns([5.4, 1.1])
            with description_col:
                st.markdown(label)
            with value_col:
                selected_value = st.selectbox(
                    label,
                    options=YES_NO_OPTIONS,
                    key=state_key,
                    label_visibility="collapsed",
                )

            final_adjustments[field_key] = selected_value == "Sim"

    return final_adjustments


def render_sinais_prontos() -> dict:
    signal_indicator_1 = READY_SIGNAL_INDICATOR_OPTIONS[0]
    signal_indicator_1_parameters = {}
    signal_indicator_2 = READY_SIGNAL_INDICATOR_OPTIONS[0]
    signal_indicator_2_parameters = {}
    signal_indicator_3 = READY_SIGNAL_INDICATOR_OPTIONS[0]
    signal_indicator_3_parameters = {}
    signal_indicator_4 = READY_SIGNAL_INDICATOR_OPTIONS[0]
    signal_indicator_4_parameters = {}
    signal_rules: list[dict] = []
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
        st.markdown(
            """
            <div class="signal-section">
                <div class="signal-section__eyebrow">Painel de Indicadores</div>
                <div class="signal-section__title">Monte a camada base dos sinais</div>
                <div class="signal-section__text">
                    Cada slot libera fontes para o motor de regras logo abaixo.
                    O Indicador 1 continua sendo o ponto de configuracao detalhada.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        indicator_row_1_col_1, indicator_row_1_col_2 = st.columns(2)
        with indicator_row_1_col_1:
            signal_indicator_1, signal_indicator_1_parameters = _render_signal_indicator_card(1)
        with indicator_row_1_col_2:
            signal_indicator_2, signal_indicator_2_parameters = _render_signal_indicator_card(2)

        indicator_row_2_col_1, indicator_row_2_col_2 = st.columns(2)
        with indicator_row_2_col_1:
            signal_indicator_3, signal_indicator_3_parameters = _render_signal_indicator_card(3)
        with indicator_row_2_col_2:
            signal_indicator_4, signal_indicator_4_parameters = _render_signal_indicator_card(4)

        st.markdown("<div class='signal-divider'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="signal-section">
                <div class="signal-section__eyebrow">Motor de Regras</div>
                <div class="signal-section__title">Combine os componentes em sequencias logicas</div>
                <div class="signal-section__text">
                    Use as fontes dos indicadores acima, campos de preco e referencias fixas para montar as condicoes.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="signal-rule-note">
                Com a vela no modo completo, podera selecionar qualquer vela do historico.
            </div>
            """,
            unsafe_allow_html=True,
        )

        signal_rule_source_options, signal_rule_source_labels = _build_signal_rule_source_options(
            [
                signal_indicator_1,
                signal_indicator_2,
                signal_indicator_3,
                signal_indicator_4,
            ]
        )

        with st.container(border=True):
            header_col_1, header_col_2, header_col_3, header_col_4, header_col_5, header_col_6 = st.columns(
                [1.35, 2.35, 1.6, 2.1, 2.35, 1.6]
            )
            header_col_1.markdown("**Comando logico**")
            header_col_2.markdown("**Fonte A**")
            header_col_3.markdown("**Candle A**")
            header_col_4.markdown("**Operador**")
            header_col_5.markdown("**Fonte B**")
            header_col_6.markdown("**Candle B**")

            for rule_index in range(SIGNAL_RULE_COUNT):
                signal_rules.append(
                    _render_signal_rule_row(
                        rule_index,
                        signal_rule_source_options,
                        signal_rule_source_labels,
                    )
                )

    return {
        "signal_settings": {
            "indicator_1": signal_indicator_1,
            "indicator_1_parameters": signal_indicator_1_parameters,
            "indicator_2": signal_indicator_2,
            "indicator_2_parameters": signal_indicator_2_parameters,
            "indicator_3": signal_indicator_3,
            "indicator_3_parameters": signal_indicator_3_parameters,
            "indicator_4": signal_indicator_4,
            "indicator_4_parameters": signal_indicator_4_parameters,
            "rules": signal_rules,
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
