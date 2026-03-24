from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from config import (
    DISTANCE_CALCULATION_OPTIONS,
    MARKET_PERIOD_OPTIONS,
    OPERATIONAL_TYPE_OPTIONS,
    ORDER_EXECUTION_OPTIONS,
    PRIMARY_TIMEFRAME_OPTIONS,
    PROCESSING_MODE_OPTIONS,
    TARGET_MARKET_OPTIONS,
    TIMEFRAME_OPTIONS,
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
from ui.components import render_risco


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
                max-width: 100%;
                padding-left: 2rem;
                padding-right: 2rem;
                padding-top: 2rem;
                padding-bottom: 3rem;
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


_init_session_state()
_apply_page_style()

st.title("AlphaForge - Strategy Builder")
st.caption("Visual builder para estrategias de trading integradas ao MetaTrader 5.")

available_symbols = st.session_state["symbols"]
market_data = st.session_state["market_data"]
market_query = st.session_state["market_query"]

top_col_1, top_col_2, top_col_3, top_col_4 = st.columns(4)

with top_col_1:
    with st.expander("Conexao MT5", expanded=True):
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

with top_col_2:
    with st.expander("Dados de mercado", expanded=True):
        selected_symbol = st.selectbox(
            "Simbolo",
            options=available_symbols if available_symbols else ["Sem simbolos disponiveis"],
            disabled=not bool(available_symbols),
        )
        selected_timeframe = st.selectbox("Timeframe", options=TIMEFRAME_OPTIONS)
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
            if not st.session_state["mt5_connected"]:
                st.error("Conecte ao MT5 antes de carregar os dados.")
            elif not available_symbols:
                st.error("Nenhum simbolo disponivel para consulta.")
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
                        selected_timeframe,
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

                if market_data.empty:
                    st.warning(get_last_error() or "Nenhum dado retornado.")
                else:
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

with top_col_3:
    with st.expander("Informacoes basicas da estrategia", expanded=True):
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

with top_col_4:
    with st.expander("Gestao de risco", expanded=True):
        risk_management = render_risco()

config_col_1, config_col_2, _, _ = st.columns(4)

with config_col_1:
    with st.expander("Configuracao inicial", expanded=True):
        primary_timeframe = st.selectbox(
            "Tempo grafico principal",
            options=PRIMARY_TIMEFRAME_OPTIONS,
            format_func=lambda value: "Corrente" if value == "CURRENT" else value,
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

with config_col_2:
    with st.expander("Tipo de ordens", expanded=True):
        distance_calculation_type = st.selectbox(
            "Tipo de calculo das distancias",
            options=DISTANCE_CALCULATION_OPTIONS,
        )
        entry_order_type = st.selectbox(
            "Ordem de entrada",
            options=ORDER_EXECUTION_OPTIONS,
        )
        exit_order_type = st.selectbox(
            "Ordens de saida",
            options=ORDER_EXECUTION_OPTIONS,
        )

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
        "primary_timeframe": primary_timeframe,
        "initial_volume": float(initial_volume),
        "max_spread": float(max_spread),
        "distance_calculation_type": distance_calculation_type,
        "entry_order_type": entry_order_type,
        "exit_order_type": exit_order_type,
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
