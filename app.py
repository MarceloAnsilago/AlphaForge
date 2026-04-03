from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from builders.rules_builder import build_entry_rules, build_exit_rules
from builders.settings_builder import build_settings
from builders.strategy_builder import build_strategy_payload
from core.backtest_engine import run_backtest
from state import get_state
from ui.backend import UiBackendContext, get_ui_backend_context
from ui.mining_pages import (
    render_backend_status,
    render_campaign_detail_page,
    render_campaigns_page,
    render_mining_pages_style,
    render_sidebar_navigation,
    render_strategy_detail_page,
)
from ui.tabs import (
    apply_page_style,
    create_main_tabs,
    render_connection_tab,
    render_final_adjustments_tab,
    render_initial_setup_tab,
    render_market_data_tab,
    render_partial_exits_tab,
    render_schedule_tab,
    render_signals_tab,
    render_soft_trailing_stop_tab,
    render_stop_loss_tab,
    render_strategy_basics_tab,
    render_take_profit_tab,
    render_trailing_stop_tab,
)


def _build_risk_management(
    stop_loss_config: dict[str, Any],
    take_profit_config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "stop": stop_loss_config["target"],
        "take": take_profit_config["target"],
    }


def _build_price_chart(market_data: pd.DataFrame, trades: pd.DataFrame) -> alt.Chart:
    price_data = market_data.loc[:, ["time", "close"]].copy()

    entry_points = trades.loc[:, ["entry_time", "entry_price", "side", "pnl"]].rename(
        columns={"entry_time": "time", "entry_price": "price"}
    )
    entry_points["event"] = "Entrada"

    exit_points = trades.loc[:, ["exit_time", "exit_price", "side", "pnl"]].rename(
        columns={"exit_time": "time", "exit_price": "price"}
    )
    exit_points["event"] = "Saida"

    trade_markers = pd.concat([entry_points, exit_points], ignore_index=True)

    price_line = (
        alt.Chart(price_data)
        .mark_line(color="#2563eb", strokeWidth=2)
        .encode(
            x=alt.X("time:T", title="Horario"),
            y=alt.Y("close:Q", title="Preco"),
            tooltip=[
                alt.Tooltip("time:T", title="Horario"),
                alt.Tooltip("close:Q", title="Fechamento", format=".5f"),
            ],
        )
    )

    marker_points = (
        alt.Chart(trade_markers)
        .mark_point(size=90, filled=True)
        .encode(
            x=alt.X("time:T", title="Horario"),
            y=alt.Y("price:Q", title="Preco"),
            color=alt.Color(
                "event:N",
                title="Evento",
                scale=alt.Scale(domain=["Entrada", "Saida"], range=["#16a34a", "#dc2626"]),
            ),
            shape=alt.Shape(
                "event:N",
                title="Evento",
                scale=alt.Scale(domain=["Entrada", "Saida"], range=["triangle-up", "triangle-down"]),
            ),
            tooltip=[
                alt.Tooltip("event:N", title="Evento"),
                alt.Tooltip("side:N", title="Lado"),
                alt.Tooltip("time:T", title="Horario"),
                alt.Tooltip("price:Q", title="Preco", format=".5f"),
                alt.Tooltip("pnl:Q", title="PnL da operacao", format=".2f"),
            ],
        )
    )

    return (price_line + marker_points).properties(height=360)


def _render_backtest(backtest_result: dict[str, Any], market_data: pd.DataFrame) -> None:
    summary = backtest_result["summary"]
    metric_columns = st.columns(6)
    metric_columns[0].metric("Trades", int(summary["total_trades"]))
    metric_columns[1].metric("Win rate", f"{summary['win_rate']:.1f}%")
    metric_columns[2].metric("Lucro liquido", f"{summary['net_profit']:.2f}")
    metric_columns[3].metric("Lucro bruto", f"{summary['gross_profit']:.2f}")
    metric_columns[4].metric("Perda bruta", f"{summary['gross_loss']:.2f}")
    metric_columns[5].metric("Max drawdown", f"{summary['max_drawdown']:.2f}")

    if backtest_result["ambiguous_entries"] > 0:
        st.warning(
            "Alguns sinais de entrada foram ignorados por ambiguidade de direcao: "
            f"{backtest_result['ambiguous_entries']} candle(s)."
        )

    trades = backtest_result["trades"]
    if trades.empty:
        st.info("Nenhuma operacao foi gerada pelo backtest simples com os candles carregados.")
        return

    performance_curve = backtest_result["performance_curve"]
    if not performance_curve.empty:
        chart_col_1, chart_col_2 = st.columns(2)
        with chart_col_1:
            st.caption("Desempenho acumulado")
            st.line_chart(performance_curve.set_index("time")[["equity"]], use_container_width=True)
        with chart_col_2:
            st.caption("Drawdown")
            st.area_chart(performance_curve.set_index("time")[["drawdown"]], use_container_width=True)

    if not market_data.empty:
        st.caption("Preco com entradas e saidas")
        st.altair_chart(_build_price_chart(market_data, trades), use_container_width=True)

    st.dataframe(trades, use_container_width=True)


def _builder_execution_parameters() -> dict[str, Any]:
    return {
        "fill_policy": "next_candle_open",
        "evaluation_mode": "manual_builder",
        "dataset_role": "full",
        "dataset_id": "builder",
        "partition_origin": "builder",
        "window_index": 0,
        "window_label": "builder",
    }


def render_builder_page(state: dict[str, Any], backend: UiBackendContext) -> None:
    st.title("AlphaForge - Strategy Builder")
    st.caption("Visual builder para estrategias de trading integradas ao MetaTrader 5.")

    main_tabs = create_main_tabs()

    render_connection_tab(main_tabs[0], state)
    market_config = render_market_data_tab(main_tabs[1], state)
    operation_config = render_strategy_basics_tab(main_tabs[2])
    time_config = render_schedule_tab(main_tabs[3])
    initial_setup_config = render_initial_setup_tab(main_tabs[4])

    stop_loss_config = render_stop_loss_tab(main_tabs[5])
    soft_trailing_stop_config = render_soft_trailing_stop_tab(main_tabs[6])
    take_profit_config = render_take_profit_tab(main_tabs[7])
    trailing_stop_config = render_trailing_stop_tab(main_tabs[8])
    partial_exits_config = render_partial_exits_tab(main_tabs[9])

    signal_config = render_signals_tab(main_tabs[10])
    final_adjustments_config = render_final_adjustments_tab(main_tabs[11])

    risk_config = {
        "stop_loss": stop_loss_config,
        "soft_trailing_stop": soft_trailing_stop_config,
        "take_profit": take_profit_config,
        "trailing_stop": trailing_stop_config,
        "partial_exits": partial_exits_config,
    }
    execution_config = {
        "distance_calculation_type": signal_config["distance_calculation_type"],
        "entry": signal_config["entry"],
        "exit": signal_config["exit"],
    }
    filter_config = {
        "candle_constraints": signal_config["candle_constraints"],
    }

    button_col_1, button_col_2, button_col_3, button_col_4 = st.columns(4)
    save_clicked = button_col_1.button("Salvar Estrutura", use_container_width=True)
    persist_strategy_clicked = button_col_2.button("Salvar no Backend", use_container_width=True)
    persist_backtest_clicked = button_col_3.button(
        "Persistir Backtest",
        use_container_width=True,
        disabled=state["market_data"].empty,
    )
    show_clicked = button_col_4.button("Exibir JSON da Estrategia", use_container_width=True)

    if save_clicked or persist_strategy_clicked or persist_backtest_clicked or show_clicked:
        entry_rules = build_entry_rules(signal_config["ready_signals"])
        exit_rules = build_exit_rules(signal_config["ready_signals"])
        settings = build_settings(
            operation_config=operation_config,
            time_config=time_config,
            risk_config=risk_config,
            execution_config=execution_config,
            filter_config=filter_config,
            ready_signals=signal_config["ready_signals"],
            final_adjustments=final_adjustments_config,
            initial_setup_config=initial_setup_config,
        )
        payload = build_strategy_payload(
            strategy_name=operation_config["strategy_name"],
            direction=operation_config["direction"],
            settings=settings,
            symbol=market_config["selected_symbol"] if state["symbols"] else None,
            timeframe=market_config["selected_timeframe"],
            period_mode=market_config["period_mode"],
            custom_start_date=market_config["custom_start_date"],
            custom_end_date=market_config["custom_end_date"],
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            risk_management=_build_risk_management(stop_loss_config, take_profit_config),
        )

        if save_clicked:
            state["saved_strategy"] = payload
            st.success("Estrutura da estrategia salva na sessao atual.")

        persisted_strategy: dict[str, Any] | None = None
        if persist_strategy_clicked or persist_backtest_clicked:
            with st.spinner("Persistindo estrategia..."):
                persisted_strategy = backend.strategy_service.ensure_strategy(payload, origin="manual")
            state["selected_strategy_version_id"] = persisted_strategy["strategy_version"]["id"]
            deduplicated = bool(persisted_strategy.get("deduplicated"))
            message = (
                "Estrategia ja existia no backend; referencia carregada com sucesso."
                if deduplicated
                else "Estrategia persistida no backend."
            )
            st.success(message)
            st.caption(
                f"Strategy ID: {persisted_strategy['strategy']['id']} | "
                f"Version ID: {persisted_strategy['strategy_version']['id']}"
            )

        if persist_backtest_clicked:
            market_data = state["market_data"]
            if persisted_strategy is None:
                persisted_strategy = backend.strategy_service.ensure_strategy(payload, origin="manual")
            with st.spinner("Executando e persistindo backtest..."):
                execution = backend.backtest_service.run_and_persist_backtest(
                    strategy_version=persisted_strategy["strategy_version"],
                    strategy=persisted_strategy["strategy_spec"],
                    candles=market_data,
                    execution_parameters=_builder_execution_parameters(),
                )
            persisted = execution["persistence"]
            run_row = persisted["backtest_run"]
            state["selected_backtest_run_id"] = run_row["id"]
            state["selected_strategy_run_ids"] = [run_row["id"]]
            state["selected_strategy_position"] = 0
            status_message = (
                "Backtest ja existia no backend; referencia carregada."
                if persisted.get("deduplicated")
                else "Backtest persistido com sucesso."
            )
            st.success(status_message)
            st.caption(f"Run ID: {run_row['id']}")
            if st.button("Abrir detalhe da estrategia", key="open-persisted-builder-run", use_container_width=True):
                state["ui_page"] = "Detalhe da Estrategia"
                st.rerun()

        st.json(payload)

        market_data = state["market_data"]
        if not market_data.empty:
            with st.expander("Backtest simples", expanded=True):
                backtest_result = run_backtest(payload, market_data)
                _render_backtest(backtest_result, market_data)
        else:
            st.info("Carregue candles do MT5 para executar o backtest simples.")


def render_app() -> None:
    st.set_page_config(page_title="AlphaForge", layout="wide")

    state = get_state()
    apply_page_style()
    render_mining_pages_style()

    backend = get_ui_backend_context()
    current_page = render_sidebar_navigation(state)
    render_backend_status(backend)

    if current_page == "Builder":
        render_builder_page(state, backend)
        return
    if current_page == "Campanhas":
        render_campaigns_page(backend, state)
        return
    if current_page == "Detalhe da Campanha":
        render_campaign_detail_page(backend, state)
        return
    render_strategy_detail_page(backend, state)


render_app()
