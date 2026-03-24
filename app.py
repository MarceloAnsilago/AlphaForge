from __future__ import annotations

import pandas as pd
import streamlit as st

from config import DIRECTION_OPTIONS, MAX_RULES, TIMEFRAME_OPTIONS
from core.strategy_schema import build_strategy_structure
from infra.mt5_gateway import get_candles, get_last_error, get_symbols, initialize_mt5
from ui.components import render_regra, render_risco


st.set_page_config(page_title="AlphaForge", layout="centered")


def _init_session_state() -> None:
    defaults = {
        "mt5_connected": False,
        "mt5_status": "",
        "symbols": [],
        "market_data": pd.DataFrame(),
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
                max-width: 980px;
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
    symbol: str | None,
    timeframe: str,
    entry_rules: list[dict],
    exit_rules: list[dict],
    risk_management: dict,
) -> dict:
    return build_strategy_structure(
        name=strategy_name,
        direction=direction,
        market={
            "symbol": symbol,
            "timeframe": timeframe,
        },
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        risk_management=risk_management,
    )


_init_session_state()
_apply_page_style()

st.title("AlphaForge - Strategy Builder")
st.caption("Visual builder para estrategias de trading integradas ao MetaTrader 5.")

with st.expander("Conexao MT5", expanded=True):
    if st.button("Conectar ao MT5", use_container_width=False):
        connected = initialize_mt5()
        st.session_state["mt5_connected"] = connected
        st.session_state["mt5_status"] = (
            "Conectado ao MetaTrader 5." if connected else get_last_error()
        )
        st.session_state["symbols"] = get_symbols() if connected else []

    if st.session_state["mt5_connected"]:
        st.success("Conexao ativa com o MetaTrader 5.")
    else:
        if st.session_state["mt5_status"]:
            st.error(st.session_state["mt5_status"])
        else:
            st.info("Clique no botao para conectar ao MetaTrader 5.")

available_symbols = st.session_state["symbols"]
market_data = st.session_state["market_data"]

with st.expander("Dados de mercado", expanded=True):
    selected_symbol = st.selectbox(
        "Simbolo",
        options=available_symbols if available_symbols else ["Sem simbolos disponiveis"],
        disabled=not bool(available_symbols),
    )
    selected_timeframe = st.selectbox("Timeframe", options=TIMEFRAME_OPTIONS)

    if st.button("Carregar dados", use_container_width=False):
        if not st.session_state["mt5_connected"]:
            st.error("Conecte ao MT5 antes de carregar os dados.")
        elif not available_symbols:
            st.error("Nenhum simbolo disponivel para consulta.")
        else:
            candles = get_candles(selected_symbol, selected_timeframe, n=500)
            st.session_state["market_data"] = candles
            market_data = candles
            if candles.empty:
                st.warning(get_last_error() or "Nenhum dado retornado.")
            else:
                st.success(f"{len(candles)} candles carregados para {selected_symbol}.")

    if not market_data.empty:
        st.dataframe(market_data, use_container_width=True)
        st.line_chart(market_data.set_index("time")[["close"]], use_container_width=True)

with st.expander("Informacoes basicas da estrategia", expanded=True):
    info_col_1, info_col_2 = st.columns(2)
    with info_col_1:
        strategy_name = st.text_input("Nome da estrategia", value="Minha Estrategia")
    with info_col_2:
        direction = st.selectbox("Direcao", options=DIRECTION_OPTIONS)

with st.expander("Regras de entrada", expanded=False):
    entry_rules = [render_regra(f"regra_entrada_{index}") for index in range(1, MAX_RULES + 1)]

with st.expander("Regras de saida", expanded=False):
    exit_rules = [render_regra(f"regra_saida_{index}") for index in range(1, MAX_RULES + 1)]

with st.expander("Gestao de risco", expanded=False):
    risk_management = render_risco()

button_col_1, button_col_2 = st.columns(2)
save_clicked = button_col_1.button("Salvar Estrutura", use_container_width=True)
show_clicked = button_col_2.button("Exibir JSON da Estrategia", use_container_width=True)

if save_clicked or show_clicked:
    payload = _build_strategy_payload(
        strategy_name=strategy_name,
        direction=direction,
        symbol=selected_symbol if available_symbols else None,
        timeframe=selected_timeframe,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        risk_management=risk_management,
    )

    if save_clicked:
        st.session_state["saved_strategy"] = payload
        st.success("Estrutura da estrategia salva na sessao atual.")

    st.json(payload)
