from __future__ import annotations

from typing import Any

import streamlit as st

from builders.rules_builder import build_entry_rules, build_exit_rules
from builders.settings_builder import build_settings
from builders.strategy_builder import build_strategy_payload
from core.backtest_engine import run_backtest
from state import get_state
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


def _render_backtest(backtest_result: dict[str, Any]) -> None:
    summary = backtest_result["summary"]
    metric_columns = st.columns(5)
    metric_columns[0].metric("Trades", int(summary["total_trades"]))
    metric_columns[1].metric("Win rate", f"{summary['win_rate']:.1f}%")
    metric_columns[2].metric("Lucro liquido", f"{summary['net_profit']:.2f}")
    metric_columns[3].metric("Lucro bruto", f"{summary['gross_profit']:.2f}")
    metric_columns[4].metric("Perda bruta", f"{summary['gross_loss']:.2f}")

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
        st.subheader("Desempenho acumulado")
        st.line_chart(performance_curve.set_index("time")[["equity"]], use_container_width=True)

    st.dataframe(trades, use_container_width=True)


def render_app() -> None:
    st.set_page_config(page_title="AlphaForge", layout="wide")

    state = get_state()
    apply_page_style()

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

    button_col_1, button_col_2, _, _ = st.columns(4)
    save_clicked = button_col_1.button("Salvar Estrutura", use_container_width=True)
    show_clicked = button_col_2.button("Exibir JSON da Estrategia", use_container_width=True)

    if save_clicked or show_clicked:
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

        st.json(payload)

        market_data = state["market_data"]
        if not market_data.empty:
            with st.expander("Backtest simples", expanded=True):
                backtest_result = run_backtest(payload, market_data)
                _render_backtest(backtest_result)
        else:
            st.info("Carregue candles do MT5 para executar o backtest simples.")


render_app()
