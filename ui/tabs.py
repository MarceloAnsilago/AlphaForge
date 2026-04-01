from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import streamlit as st

from builders.settings_builder import build_order_config, build_time_config
from builders.strategy_builder import PERIOD_LABELS, derive_direction, format_timeframe_label, resolve_market_timeframe
from config import (
    DISTANCE_CALCULATION_OPTIONS,
    MARKET_PERIOD_OPTIONS,
    OPERATIONAL_TYPE_OPTIONS,
    PRIMARY_TIMEFRAME_OPTIONS,
    PROCESSING_MODE_OPTIONS,
    TARGET_MARKET_OPTIONS,
    YES_NO_OPTIONS,
)
from services.mt5_service import connect_terminal, load_market_data, load_terminal_symbols
from ui.components import (
    render_ajustes_finais,
    render_saidas_parciais,
    render_sinais_prontos,
    render_stop_loss,
    render_stop_movel,
    render_take_profit,
    render_trailing_stop,
)


TAB_TITLES = [
    "1. Conexao MT5",
    "2. Dados de mercado",
    "3. Informacoes basicas da estrategia",
    "4. Horario",
    "5. Configuracao inicial",
    "6. Stop loss",
    "7. Stop movel",
    "8. Take profit",
    "9. Trailing stop",
    "10. Saidas parciais",
    "11. Sinais",
    "12. Ajustes finais",
]


def apply_page_style() -> None:
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

            .signal-section {
                background: linear-gradient(135deg, rgba(37, 99, 235, 0.10), rgba(14, 165, 233, 0.06));
                border: 1px solid rgba(37, 99, 235, 0.12);
                border-radius: 18px;
                padding: 1rem 1.1rem;
                margin: 0.35rem 0 1rem 0;
            }

            .signal-section__eyebrow {
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: #315b96;
                margin-bottom: 0.2rem;
            }

            .signal-section__title {
                font-size: 1.05rem;
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 0.2rem;
            }

            .signal-section__text {
                font-size: 0.9rem;
                color: #475569;
            }

            .signal-divider {
                height: 1px;
                border: 0;
                background: linear-gradient(90deg, rgba(148, 163, 184, 0.05), rgba(37, 99, 235, 0.42), rgba(148, 163, 184, 0.05));
                margin: 1rem 0 1rem 0;
            }

            .signal-card-title {
                font-size: 0.84rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                color: #315b96;
                margin-bottom: 0.4rem;
            }

            .signal-card-meta {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
                margin: 0.35rem 0 0.15rem 0;
            }

            .signal-card-badge {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.18rem 0.6rem;
                background: #eef4ff;
                border: 1px solid #d9e5ff;
                color: #214d86;
                font-size: 0.78rem;
                font-weight: 600;
            }

            .signal-card-summary {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.18rem 0.6rem;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                color: #475569;
                font-size: 0.78rem;
            }

            .signal-rule-note {
                background: #f8fafc;
                border: 1px dashed #d5dfed;
                border-radius: 12px;
                padding: 0.7rem 0.85rem;
                color: #475569;
                font-size: 0.86rem;
                margin-bottom: 0.85rem;
            }

            [data-baseweb="select"] > div {
                min-height: 2.45rem;
                padding-top: 0.1rem;
                padding-bottom: 0.1rem;
            }

            [data-baseweb="select"] span,
            [data-baseweb="select"] input,
            [data-baseweb="select"] div {
                font-size: 0.82rem !important;
            }

            [role="listbox"] [role="option"] {
                font-size: 0.82rem !important;
                line-height: 1.2;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def create_main_tabs() -> list[Any]:
    return st.tabs(TAB_TITLES)


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
        st.markdown(
            "<div style='text-align:center; padding-top: 0.35rem;'>:</div>",
            unsafe_allow_html=True,
        )

    with minute_col:
        minute = st.selectbox(
            f"{label} minuto",
            options=minute_options,
            index=default_minute,
            key=f"{key_prefix}_minute",
            label_visibility="collapsed",
        )

    return int(hour), int(minute)


def render_connection_tab(tab: Any, state: dict[str, Any]) -> None:
    with tab:
        with st.expander("Conexao MT5", expanded=False):
            connect_col, load_symbols_col = st.columns(2)

            if connect_col.button("Conectar ao MT5", use_container_width=True):
                connection_result = connect_terminal()
                state["mt5_connected"] = connection_result["connected"]
                state["mt5_status"] = connection_result["status"]
                if connection_result["connected"]:
                    symbols_result = load_terminal_symbols()
                    state["symbols"] = symbols_result["symbols"]
                    state["symbols_status"] = symbols_result["status"]
                else:
                    state["symbols"] = []
                    state["symbols_status"] = ""

            if load_symbols_col.button(
                "Carregar simbolos",
                use_container_width=True,
                disabled=not state["mt5_connected"],
            ):
                symbols_result = load_terminal_symbols()
                state["symbols"] = symbols_result["symbols"]
                state["symbols_status"] = symbols_result["status"]

            if state["mt5_connected"]:
                st.success("Conexao ativa com o MetaTrader 5.")
            elif state["mt5_status"]:
                st.error(state["mt5_status"])
            else:
                st.info("Clique no botao para conectar ao MetaTrader 5.")

            if state["mt5_connected"] and not state["symbols"]:
                st.info(
                    "Conexao realizada, mas nenhum simbolo foi carregado automaticamente. "
                    "Use 'Carregar simbolos' para tentar novamente."
                )

            if state["symbols_status"]:
                if state["symbols"]:
                    st.caption(state["symbols_status"])
                else:
                    st.warning(state["symbols_status"])


def render_market_data_tab(tab: Any, state: dict[str, Any]) -> dict[str, Any]:
    market_data = state["market_data"]
    market_query = state["market_query"]
    available_symbols = state["symbols"]
    show_market_chart = state["show_market_chart"]

    with tab:
        with st.expander("Dados de mercado", expanded=False):
            selected_symbol = st.selectbox(
                "Simbolo",
                options=available_symbols if available_symbols else ["Sem simbolos disponiveis"],
                disabled=not bool(available_symbols),
            )
            selected_timeframe = st.selectbox(
                "Tempo grafico",
                options=PRIMARY_TIMEFRAME_OPTIONS,
                format_func=format_timeframe_label,
                key="market_timeframe",
            )
            period_mode = st.selectbox(
                "Periodo de cotacoes",
                options=MARKET_PERIOD_OPTIONS,
                format_func=lambda value: PERIOD_LABELS[value],
            )
            load_clicked = st.button("Carregar dados", use_container_width=True)

            custom_start_date: date | None = None
            custom_end_date: date | None = None
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
                if not state["mt5_connected"]:
                    st.error("Conecte ao MT5 antes de carregar os dados.")
                elif not available_symbols:
                    st.error("Nenhum simbolo disponivel para consulta.")
                else:
                    effective_market_timeframe = resolve_market_timeframe(
                        selected_timeframe,
                        str(state.get("primary_timeframe", "CURRENT")),
                    )
                    if effective_market_timeframe is None:
                        st.error(
                            "Selecione um tempo grafico principal diferente de Corrente para carregar os dados de mercado."
                        )
                    else:
                        with st.spinner("Baixando candles do MT5..."):
                            market_result = load_market_data(
                                selected_symbol,
                                effective_market_timeframe,
                                period_mode,
                                custom_start_date,
                                custom_end_date,
                            )
                        if market_result["query"] is None and market_result["error"]:
                            st.error(market_result["error"])
                        else:
                            state["market_data"] = market_result["data"]
                            state["market_query"] = market_result["query"]
                            state["show_market_chart"] = False
                            market_data = state["market_data"]
                            market_query = state["market_query"]
                            show_market_chart = state["show_market_chart"]
                            if market_data.empty:
                                st.warning(market_result["error"] or "Nenhum dado retornado.")
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

                chart_button_label = "Ocultar grafico" if show_market_chart else "Exibir grafico"
                if st.button(chart_button_label, key="toggle_market_chart", use_container_width=True):
                    state["show_market_chart"] = not show_market_chart
                    show_market_chart = state["show_market_chart"]

                if show_market_chart:
                    st.line_chart(market_data.set_index("time")[["close"]], use_container_width=True)
                else:
                    st.caption("O grafico permanece oculto ate voce clicar em 'Exibir grafico'.")

    return {
        "selected_symbol": selected_symbol,
        "selected_timeframe": selected_timeframe,
        "period_mode": period_mode,
        "custom_start_date": custom_start_date,
        "custom_end_date": custom_end_date,
    }


def render_strategy_basics_tab(tab: Any) -> dict[str, Any]:
    with tab:
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
            operate_buy_label = st.radio(
                "Deseja operar na compra?",
                options=YES_NO_OPTIONS,
                horizontal=True,
            )
            operate_sell_label = st.radio(
                "Deseja operar na venda?",
                options=YES_NO_OPTIONS,
                horizontal=True,
            )

            direction = derive_direction(operate_buy_label, operate_sell_label)
            if direction == "NONE":
                st.warning(
                    "Ative compra, venda ou ambas para que a estrategia tenha direcao operacional."
                )
            else:
                st.caption(f"Direcao derivada: {direction}")

    return {
        "strategy_name": strategy_name,
        "desired_market": desired_market,
        "operational_type": operational_type,
        "processing_mode": processing_mode,
        "operate_buy": operate_buy_label == "Sim",
        "operate_sell": operate_sell_label == "Sim",
        "direction": direction,
    }


def render_schedule_tab(tab: Any) -> dict[str, Any]:
    with tab:
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

    return build_time_config(
        close_by_schedule,
        close_operations_hour,
        close_operations_minute,
        operation_start_hour,
        operation_start_minute,
        operation_end_hour,
        operation_end_minute,
    )


def render_initial_setup_tab(tab: Any) -> dict[str, Any]:
    with tab:
        with st.expander("Configuracao inicial", expanded=False):
            primary_timeframe = st.selectbox(
                "Tempo grafico principal",
                options=PRIMARY_TIMEFRAME_OPTIONS,
                format_func=format_timeframe_label,
                key="primary_timeframe",
            )
            initial_volume = float(
                st.number_input(
                    "Volume inicial",
                    min_value=0.01,
                    value=1.0,
                    step=0.01,
                    format="%.2f",
                )
            )
            max_spread = float(
                st.number_input(
                    "Spread maximo",
                    min_value=0.0,
                    value=10.0,
                    step=0.1,
                    format="%.1f",
                )
            )

    return {
        "primary_timeframe": primary_timeframe,
        "initial_volume": initial_volume,
        "max_spread": max_spread,
    }


def render_stop_loss_tab(tab: Any) -> dict[str, Any]:
    with tab:
        with st.expander("Stop loss", expanded=False):
            return render_stop_loss()


def render_soft_trailing_stop_tab(tab: Any) -> dict[str, Any]:
    with tab:
        with st.expander("Stop movel", expanded=False):
            return render_stop_movel()


def render_take_profit_tab(tab: Any) -> dict[str, Any]:
    with tab:
        with st.expander("Take profit", expanded=False):
            return render_take_profit()


def render_trailing_stop_tab(tab: Any) -> dict[str, Any]:
    with tab:
        with st.expander("Trailing stop", expanded=False):
            return render_trailing_stop()


def render_partial_exits_tab(tab: Any) -> dict[str, Any]:
    with tab:
        with st.expander("Saidas parciais", expanded=False):
            return render_saidas_parciais()


def render_signals_tab(tab: Any) -> dict[str, Any]:
    with tab:
        with st.expander("Filtro de vela", expanded=False):
            measure_type = st.selectbox(
                "Medir em",
                options=DISTANCE_CALCULATION_OPTIONS,
                key="candle_filter_measure_type",
            )
            timeframe = st.selectbox(
                "Tempo grafico",
                options=PRIMARY_TIMEFRAME_OPTIONS,
                format_func=format_timeframe_label,
                key="candle_filter_timeframe",
            )
            measure_label = "Em pontos" if measure_type == "Pontos" else "Em percentual"
            measure_step = 1.0 if measure_type == "Pontos" else 0.1
            candle_constraints = {
                "measure_type": measure_type,
                "timeframe": timeframe,
                "min_size": float(
                    st.number_input(
                        f"Tamanho minimo da vela - pavios ({measure_label})",
                        min_value=0.0,
                        value=0.0,
                        step=measure_step,
                        key="candle_filter_min_size",
                    )
                ),
                "max_size": float(
                    st.number_input(
                        f"Tamanho maximo da vela - pavios ({measure_label})",
                        min_value=0.0,
                        value=0.0,
                        step=measure_step,
                        key="candle_filter_max_size",
                    )
                ),
                "min_body": float(
                    st.number_input(
                        f"Minimo do corpo da vela ({measure_label})",
                        min_value=0.0,
                        value=0.0,
                        step=measure_step,
                        key="candle_filter_min_body",
                    )
                ),
                "max_body": float(
                    st.number_input(
                        f"Maximo do corpo da vela ({measure_label})",
                        min_value=0.0,
                        value=0.0,
                        step=measure_step,
                        key="candle_filter_max_body",
                    )
                ),
            }

        with st.expander("Tipo de ordens", expanded=False):
            distance_calculation_type = st.selectbox(
                "Tipo de calculo das distancias",
                options=DISTANCE_CALCULATION_OPTIONS,
                key="distance_calculation_type",
            )
            entry_order_col, exit_order_col = st.columns(2)

            with entry_order_col:
                entry_config = build_order_config("entry")
            with exit_order_col:
                exit_config = build_order_config("exit")

        ready_signals = render_sinais_prontos()

    return {
        "candle_constraints": candle_constraints,
        "distance_calculation_type": distance_calculation_type,
        "entry": entry_config,
        "exit": exit_config,
        "ready_signals": ready_signals,
    }


def render_final_adjustments_tab(tab: Any) -> dict[str, Any]:
    with tab:
        with st.expander("Ajustes finais", expanded=False):
            return render_ajustes_finais()
