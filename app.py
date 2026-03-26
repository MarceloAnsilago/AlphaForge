from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from config import (
    DISTANCE_CALCULATION_OPTIONS,
    MARKET_PERIOD_OPTIONS,
    OPERATIONAL_TYPE_OPTIONS,
    ORDER_EXECUTION_OPTIONS,
    PENDING_EXPIRATION_OPTIONS,
    PENDING_CANDLE_REFERENCE_OPTIONS,
    PENDING_POSITION_OPTIONS,
    PENDING_PRICE_REFERENCE_OPTIONS,
    PRIMARY_TIMEFRAME_OPTIONS,
    PROCESSING_MODE_OPTIONS,
    TARGET_MARKET_OPTIONS,
    YES_NO_OPTIONS,
)
from core.strategy_schema import build_strategy_structure
from infra.mt5_gateway import (
    build_market_period_range,
    get_candles_by_range,
    get_last_error,
    get_symbols,
    initialize_mt5,
)
from ui.components import (
    render_stop_loss,
    render_stop_movel,
    render_take_profit,
    render_trailing_stop,
)


st.set_page_config(page_title="AlphaForge", layout="wide")

PERIOD_LABELS = {
    "LAST_MONTH": "Ultimo mes",
    "LAST_YEAR": "Ultimo ano",
    "FULL_HISTORY": "Historico completo",
    "CUSTOM": "Periodo personalizado",
}

def _init_session_state() -> None:
    defaults = {
        "mt5_connected": False,
        "mt5_status": "",
        "symbols": [],
        "market_data": pd.DataFrame(),
        "market_query": None,
        "saved_strategy": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _apply_page_style() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1100px;
                margin: 0 auto;
                padding-left: 1.5rem;
                padding-right: 1.5rem;
                padding-top: 2rem;
                padding-bottom: 3rem;
            }

            [data-testid="stTabs"] {
                width: 100%;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_strategy_payload(
    strategy_name: str,
    direction: str,
    settings: dict,
    symbol: str | None,
    timeframe: str,
    period_mode: str,
    custom_start_date: date | None,
    custom_end_date: date | None,
    entry_rules: list[dict],
    exit_rules: list[dict],
    risk_management: dict,
) -> dict:
    market_context = {
        "symbol": symbol,
        "timeframe": timeframe,
        "quote_period": period_mode,
    }
    if period_mode == "CUSTOM":
        market_context["start_date"] = (
            custom_start_date.isoformat() if custom_start_date is not None else None
        )
        market_context["end_date"] = (
            custom_end_date.isoformat() if custom_end_date is not None else None
        )

    return build_strategy_structure(
        name=strategy_name,
        direction=direction,
        settings=settings,
        market=market_context,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        risk_management=risk_management,
    )


def _derive_direction(operate_buy: str, operate_sell: str) -> str:
    buy_enabled = operate_buy == "Sim"
    sell_enabled = operate_sell == "Sim"

    if buy_enabled and sell_enabled:
        return "BOTH"
    if buy_enabled:
        return "BUY"
    if sell_enabled:
        return "SELL"
    return "NONE"


def _format_timeframe_label(value: str) -> str:
    return "Corrente" if value == "CURRENT" else value


def _resolve_market_timeframe(selected_timeframe: str) -> str | None:
    if selected_timeframe != "CURRENT":
        return selected_timeframe

    primary_timeframe = st.session_state.get("primary_timeframe", "CURRENT")
    if primary_timeframe == "CURRENT":
        return None

    return primary_timeframe


def _render_hour_minute_input(
    label: str,
    key_prefix: str,
    default_hour: int,
    default_minute: int,
) -> tuple[int, int]:
    st.caption(label)
    hour_col, colon_col, minute_col = st.columns([1, 0.2, 1])
    hour_options = [f"{value:02d}" for value in range(25)]
    minute_options = [f"{value:02d}" for value in range(60)]

    with hour_col:
        hour = st.selectbox(
            f"{label} hora",
            options=hour_options,
            index=default_hour,
            key=f"{key_prefix}_hour",
            label_visibility="collapsed",
        )

    with colon_col:
        st.markdown("<div style='text-align:center; padding-top: 0.35rem;'>:</div>", unsafe_allow_html=True)

    with minute_col:
        minute = st.selectbox(
            f"{label} minuto",
            options=minute_options,
            index=default_minute,
            key=f"{key_prefix}_minute",
            label_visibility="collapsed",
        )

    return int(hour), int(minute)


_init_session_state()
_apply_page_style()

st.title("AlphaForge - Strategy Builder")
st.caption("Visual builder para estrategias de trading integradas ao MetaTrader 5.")

available_symbols = st.session_state["symbols"]
market_data = st.session_state["market_data"]
market_query = st.session_state["market_query"]

main_tabs = st.tabs(
    [
        "1. Conexao MT5",
        "2. Dados de mercado",
        "3. Informacoes basicas da estrategia",
        "4. Horario",
        "5. Configuracao inicial",
        "6. Tipo de ordens",
        "7. Filtro de vela",
        "8. Stop loss",
        "9. Stop movel",
        "10. Take profit",
        "11. Trailing stop",
    ]
)

with main_tabs[0]:
    with st.expander("Conexao MT5", expanded=False):
        if st.button("Conectar ao MT5", use_container_width=True):
            connected = initialize_mt5()
            st.session_state["mt5_connected"] = connected
            st.session_state["mt5_status"] = (
                "Conectado ao MetaTrader 5." if connected else get_last_error()
            )
            st.session_state["symbols"] = get_symbols() if connected else []
            available_symbols = st.session_state["symbols"]

        if st.session_state["mt5_connected"]:
            st.success("Conexao ativa com o MetaTrader 5.")
        else:
            if st.session_state["mt5_status"]:
                st.error(st.session_state["mt5_status"])
            else:
                st.info("Clique no botao para conectar ao MetaTrader 5.")

with main_tabs[1]:
    with st.expander("Dados de mercado", expanded=False):
        selected_symbol = st.selectbox(
            "Simbolo",
            options=available_symbols if available_symbols else ["Sem simbolos disponiveis"],
            disabled=not bool(available_symbols),
        )
        selected_timeframe = st.selectbox(
            "Tempo grafico",
            options=PRIMARY_TIMEFRAME_OPTIONS,
            format_func=_format_timeframe_label,
            key="market_timeframe",
        )
        period_mode = st.selectbox(
            "Periodo de cotacoes",
            options=MARKET_PERIOD_OPTIONS,
            format_func=lambda value: PERIOD_LABELS[value],
        )
        load_clicked = st.button("Carregar dados", use_container_width=True)

        custom_start_date = None
        custom_end_date = None
        if period_mode == "CUSTOM":
            custom_start_date = st.date_input(
                "Data inicial",
                value=date.today() - timedelta(days=30),
            )
            custom_end_date = st.date_input(
                "Data final",
                value=date.today(),
            )

        if load_clicked:
            load_feedback = False
            if not st.session_state["mt5_connected"]:
                st.error("Conecte ao MT5 antes de carregar os dados.")
            elif not available_symbols:
                st.error("Nenhum simbolo disponivel para consulta.")
            else:
                effective_market_timeframe = _resolve_market_timeframe(selected_timeframe)
                if effective_market_timeframe is None:
                    st.error(
                        "Selecione um tempo grafico principal diferente de Corrente para carregar os dados de mercado."
                    )
                else:
                    period_range = build_market_period_range(
                        period_mode,
                        start_date=custom_start_date,
                        end_date=custom_end_date,
                    )
                    if period_range is None:
                        st.error(get_last_error())
                    else:
                        start, end = period_range
                        candles = get_candles_by_range(
                            selected_symbol,
                            effective_market_timeframe,
                            start=start,
                            end=end,
                        )
                        st.session_state["market_data"] = candles
                        st.session_state["market_query"] = {
                            "period_mode": period_mode,
                            "custom_start_date": custom_start_date.isoformat()
                            if custom_start_date is not None
                            else None,
                            "custom_end_date": custom_end_date.isoformat()
                            if custom_end_date is not None
                            else None,
                        }
                        market_data = candles
                        market_query = st.session_state["market_query"]
                        load_feedback = True

                if load_feedback and market_data.empty:
                    st.warning(get_last_error() or "Nenhum dado retornado.")
                elif load_feedback:
                    st.success(f"{len(market_data)} candles carregados para {selected_symbol}.")

        if not market_data.empty:
            loaded_period_mode = market_query["period_mode"] if market_query else period_mode
            st.caption(
                f"Periodo selecionado: {PERIOD_LABELS[loaded_period_mode]}"
                + (
                    f" ({market_query['custom_start_date']} ate {market_query['custom_end_date']})"
                    if market_query
                    and loaded_period_mode == "CUSTOM"
                    and market_query["custom_start_date"]
                    and market_query["custom_end_date"]
                    else ""
                )
            )
            st.dataframe(market_data, use_container_width=True)
            st.line_chart(market_data.set_index("time")[["close"]], use_container_width=True)

with main_tabs[2]:
    with st.expander("Informacoes basicas da estrategia", expanded=False):
        strategy_name = st.text_input("Nome da estrategia", value="Minha Estrategia")
        desired_market = st.selectbox("Mercado desejado", options=TARGET_MARKET_OPTIONS)
        operational_type = st.selectbox(
            "Tipo operacional",
            options=OPERATIONAL_TYPE_OPTIONS,
        )
        processing_mode = st.selectbox(
            "Modo de processamento",
            options=PROCESSING_MODE_OPTIONS,
        )
        operate_buy = st.radio(
            "Deseja operar na compra?",
            options=YES_NO_OPTIONS,
            horizontal=True,
        )
        operate_sell = st.radio(
            "Deseja operar na venda?",
            options=YES_NO_OPTIONS,
            horizontal=True,
        )

        direction = _derive_direction(operate_buy, operate_sell)
        if direction == "NONE":
            st.warning("Ative compra, venda ou ambas para que a estrategia tenha direcao operacional.")
        else:
            st.caption(f"Direcao derivada: {direction}")

with main_tabs[3]:
    with st.expander("Horario", expanded=False):
        close_by_schedule = st.selectbox(
            "Deseja zerar por horario",
            options=YES_NO_OPTIONS,
            key="close_by_schedule",
        )
        close_operations_hour, close_operations_minute = 23, 0
        if close_by_schedule == "Sim":
            close_operations_hour, close_operations_minute = _render_hour_minute_input(
                "Horario de zerar as operacoes",
                "close_operations",
                23,
                0,
            )
        st.caption(
            "Para operar independente de horario, basta deixar o horario inicial igual ao horario final."
        )
        operation_start_hour, operation_start_minute = _render_hour_minute_input(
            "Horario inicial das operacoes",
            "operation_start",
            0,
            0,
        )
        operation_end_hour, operation_end_minute = _render_hour_minute_input(
            "Horario final das operacoes",
            "operation_end",
            22,
            0,
        )

with main_tabs[4]:
    with st.expander("Configuracao inicial", expanded=False):
        primary_timeframe = st.selectbox(
            "Tempo grafico principal",
            options=PRIMARY_TIMEFRAME_OPTIONS,
            format_func=_format_timeframe_label,
            key="primary_timeframe",
        )
        initial_volume = st.number_input(
            "Volume inicial",
            min_value=0.01,
            value=1.0,
            step=0.01,
            format="%.2f",
        )
        max_spread = st.number_input(
            "Spread maximo",
            min_value=0.0,
            value=10.0,
            step=0.1,
            format="%.1f",
        )

with main_tabs[5]:
    with st.expander("Tipo de ordens", expanded=False):
        distance_calculation_type = st.selectbox(
            "Tipo de calculo das distancias",
            options=DISTANCE_CALCULATION_OPTIONS,
            key="distance_calculation_type",
        )
        distance_step = 1.0 if distance_calculation_type == "Pontos" else 0.1
        entry_order_col, exit_order_col = st.columns(2)

        with entry_order_col:
            entry_order_type = st.selectbox(
                "Ordem de entrada",
                options=ORDER_EXECUTION_OPTIONS,
                key="entry_order_type",
            )
            entry_pending_positioning = None
            entry_pending_average_candles = None
            entry_pending_price_reference = None
            entry_pending_candle_reference = None
            entry_pending_order_distance = None
            entry_pending_expiration = None
            if entry_order_type == "Pendente":
                entry_pending_positioning = st.selectbox(
                    "Posicionar",
                    options=PENDING_POSITION_OPTIONS,
                    key="entry_pending_positioning",
                )
                if entry_pending_positioning == "Media":
                    entry_pending_average_candles = st.number_input(
                        "Quantidade de candles para media",
                        min_value=1,
                        value=3,
                        step=1,
                        key="entry_pending_average_candles",
                    )
                entry_pending_price_reference = st.selectbox(
                    "Referencia de preco",
                    options=PENDING_PRICE_REFERENCE_OPTIONS,
                    key="entry_pending_price_reference",
                )
                if entry_pending_positioning == "Referencia de preco":
                    entry_pending_candle_reference = st.selectbox(
                        "Candle",
                        options=PENDING_CANDLE_REFERENCE_OPTIONS,
                        key="entry_pending_candle_reference",
                    )
                entry_pending_order_distance = st.number_input(
                    f"Distancia da ordem ({distance_calculation_type})",
                    min_value=0.0,
                    value=0.0,
                    step=distance_step,
                    key="entry_pending_order_distance",
                )
                entry_pending_expiration = st.selectbox(
                    "Expiracao da ordem em candles futuros",
                    options=PENDING_EXPIRATION_OPTIONS,
                    format_func=lambda value: value if value == "Nao expirar" else f"{value} candle(s)",
                    key="entry_pending_expiration",
                )

        with exit_order_col:
            exit_order_type = st.selectbox(
                "Ordem de saida",
                options=ORDER_EXECUTION_OPTIONS,
                key="exit_order_type",
            )
            exit_pending_positioning = None
            exit_pending_average_candles = None
            exit_pending_price_reference = None
            exit_pending_candle_reference = None
            exit_pending_order_distance = None
            exit_pending_expiration = None
            if exit_order_type == "Pendente":
                exit_pending_positioning = st.selectbox(
                    "Posicionar",
                    options=PENDING_POSITION_OPTIONS,
                    key="exit_pending_positioning",
                )
                if exit_pending_positioning == "Media":
                    exit_pending_average_candles = st.number_input(
                        "Quantidade de candles para media",
                        min_value=1,
                        value=3,
                        step=1,
                        key="exit_pending_average_candles",
                    )
                exit_pending_price_reference = st.selectbox(
                    "Referencia de preco",
                    options=PENDING_PRICE_REFERENCE_OPTIONS,
                    key="exit_pending_price_reference",
                )
                if exit_pending_positioning == "Referencia de preco":
                    exit_pending_candle_reference = st.selectbox(
                        "Candle",
                        options=PENDING_CANDLE_REFERENCE_OPTIONS,
                        key="exit_pending_candle_reference",
                    )
                exit_pending_order_distance = st.number_input(
                    f"Distancia da ordem ({distance_calculation_type})",
                    min_value=0.0,
                    value=0.0,
                    step=distance_step,
                    key="exit_pending_order_distance",
                )
                exit_pending_expiration = st.selectbox(
                    "Expiracao da ordem em candles futuros",
                    options=PENDING_EXPIRATION_OPTIONS,
                    format_func=lambda value: value if value == "Nao expirar" else f"{value} candle(s)",
                    key="exit_pending_expiration",
                )

with main_tabs[6]:
    with st.expander("Filtro de vela", expanded=False):
        candle_filter_measure_type = st.selectbox(
            "Medir em",
            options=DISTANCE_CALCULATION_OPTIONS,
            key="candle_filter_measure_type",
        )
        candle_filter_timeframe = st.selectbox(
            "Tempo grafico",
            options=PRIMARY_TIMEFRAME_OPTIONS,
            format_func=_format_timeframe_label,
            key="candle_filter_timeframe",
        )
        candle_filter_measure_label = (
            "Em pontos" if candle_filter_measure_type == "Pontos" else "Em percentual"
        )
        candle_filter_measure_step = 1.0 if candle_filter_measure_type == "Pontos" else 0.1
        candle_filter_min_size = st.number_input(
            f"Tamanho minimo da vela ({candle_filter_measure_label})",
            min_value=0.0,
            value=0.0,
            step=candle_filter_measure_step,
            key="candle_filter_min_size",
        )
        candle_filter_max_size = st.number_input(
            f"Tamanho maximo da vela ({candle_filter_measure_label})",
            min_value=0.0,
            value=0.0,
            step=candle_filter_measure_step,
            key="candle_filter_max_size",
        )
        candle_filter_min_body = st.number_input(
            f"Minimo do corpo da vela ({candle_filter_measure_label})",
            min_value=0.0,
            value=0.0,
            step=candle_filter_measure_step,
            key="candle_filter_min_body",
        )
        candle_filter_max_body = st.number_input(
            f"Maximo do corpo da vela ({candle_filter_measure_label})",
            min_value=0.0,
            value=0.0,
            step=candle_filter_measure_step,
            key="candle_filter_max_body",
        )

with main_tabs[7]:
    with st.expander("Stop loss", expanded=False):
        stop_loss_config = render_stop_loss()

with main_tabs[8]:
    with st.expander("Stop movel", expanded=False):
        stop_movel_config = render_stop_movel()

with main_tabs[9]:
    with st.expander("Take profit", expanded=False):
        take_profit_config = render_take_profit()

with main_tabs[10]:
    with st.expander("Trailing stop", expanded=False):
        trailing_stop_config = render_trailing_stop()

risk_management = {
    "stop": stop_loss_config["target"],
    "take": take_profit_config["target"],
}

entry_rules = []
exit_rules = []

button_col_1, button_col_2, _, _ = st.columns(4)
save_clicked = button_col_1.button("Salvar Estrutura", use_container_width=True)
show_clicked = button_col_2.button("Exibir JSON da Estrategia", use_container_width=True)

if save_clicked or show_clicked:
    settings = {
        "operate_buy": operate_buy == "Sim",
        "operate_sell": operate_sell == "Sim",
        "desired_market": desired_market,
        "operational_type": operational_type,
        "processing_mode": processing_mode,
        "close_by_schedule": close_by_schedule == "Sim",
        "operation_start_time": f"{operation_start_hour:02d}:{operation_start_minute:02d}",
        "operation_end_time": f"{operation_end_hour:02d}:{operation_end_minute:02d}",
        "close_operations_time": f"{close_operations_hour:02d}:{close_operations_minute:02d}",
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
        "custom_stop_movel": stop_movel_config["enabled"],
        "stop_movel_calculation_type": stop_movel_config["calculation_type"],
        "stop_movel_type": stop_movel_config["type"],
        "stop_movel_acionar_a_favor": stop_movel_config["acionar_a_favor"],
        "stop_movel_passe": stop_movel_config["passe"],
        "stop_movel_distance": stop_movel_config["distance"],
        "stop_movel_candle_count": stop_movel_config["candle_count"],
        "stop_movel_reference": stop_movel_config["reference"],
        "custom_trailing_stop": trailing_stop_config["enabled"],
        "trailing_stop_type": trailing_stop_config["type"],
        "trailing_stop_distance": trailing_stop_config["distance"],
        "primary_timeframe": primary_timeframe,
        "initial_volume": float(initial_volume),
        "max_spread": float(max_spread),
        "distance_calculation_type": distance_calculation_type,
        "entry_order_type": entry_order_type,
        "exit_order_type": exit_order_type,
        "entry_pending_positioning": entry_pending_positioning,
        "entry_pending_average_candles": entry_pending_average_candles,
        "entry_pending_price_reference": entry_pending_price_reference,
        "entry_pending_candle_reference": entry_pending_candle_reference,
        "entry_pending_order_distance": entry_pending_order_distance,
        "entry_pending_expiration": entry_pending_expiration,
        "exit_pending_positioning": exit_pending_positioning,
        "exit_pending_average_candles": exit_pending_average_candles,
        "exit_pending_price_reference": exit_pending_price_reference,
        "exit_pending_candle_reference": exit_pending_candle_reference,
        "exit_pending_order_distance": exit_pending_order_distance,
        "exit_pending_expiration": exit_pending_expiration,
        "candle_filter_timeframe": candle_filter_timeframe,
        "candle_filter_measure_type": candle_filter_measure_type,
        "candle_filter_min_size": candle_filter_min_size,
        "candle_filter_max_size": candle_filter_max_size,
        "candle_filter_min_body": candle_filter_min_body,
        "candle_filter_max_body": candle_filter_max_body,
    }
    payload = _build_strategy_payload(
        strategy_name=strategy_name,
        direction=direction,
        settings=settings,
        symbol=selected_symbol if available_symbols else None,
        timeframe=selected_timeframe,
        period_mode=period_mode,
        custom_start_date=custom_start_date,
        custom_end_date=custom_end_date,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        risk_management=risk_management,
    )

    if save_clicked:
        st.session_state["saved_strategy"] = payload
        st.success("Estrutura da estrategia salva na sessao atual.")

    st.json(payload)
