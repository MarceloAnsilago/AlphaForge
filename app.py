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
from ui.builder_helpers import (
    build_builder_attempt_record,
    build_builder_attempts_frame,
    build_market_signature,
    resolve_previous_attempt,
)
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


def _build_builder_payload(
    *,
    market_config: dict[str, Any],
    operation_config: dict[str, Any],
    time_config: dict[str, Any],
    initial_setup_config: dict[str, Any],
    stop_loss_config: dict[str, Any],
    take_profit_config: dict[str, Any],
    risk_config: dict[str, Any],
    execution_config: dict[str, Any],
    filter_config: dict[str, Any],
    signal_config: dict[str, Any],
    final_adjustments_config: dict[str, Any],
) -> dict[str, Any]:
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
    return build_strategy_payload(
        strategy_name=operation_config["strategy_name"],
        direction=operation_config["direction"],
        settings=settings,
        symbol=market_config["selected_symbol"] or None,
        timeframe=market_config["selected_timeframe"],
        period_mode=market_config["period_mode"],
        custom_start_date=market_config["custom_start_date"],
        custom_end_date=market_config["custom_end_date"],
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        risk_management=_build_risk_management(stop_loss_config, take_profit_config),
    )


def _store_builder_attempt(
    *,
    state: dict[str, Any],
    payload: dict[str, Any],
    signal_config: dict[str, Any],
    backtest_result: dict[str, Any],
) -> dict[str, Any]:
    state["builder_attempt_counter"] = int(state.get("builder_attempt_counter", 0)) + 1
    attempt = build_builder_attempt_record(
        attempt_number=int(state["builder_attempt_counter"]),
        strategy_name=str(payload.get("name") or ""),
        ready_signals=signal_config["ready_signals"],
        payload=payload,
        backtest_result=backtest_result,
        market_signature=build_market_signature(state["market_data"], state.get("market_query")),
    )
    attempts = list(state.get("builder_attempts") or [])
    attempts.append(attempt)
    state["builder_attempts"] = attempts[-25:]
    state["builder_selected_attempt_id"] = attempt["id"]
    state["builder_last_payload"] = payload
    state["builder_last_backtest"] = attempt
    return attempt


def _format_metric_delta(current: float, previous: float) -> str:
    return f"{current - previous:+.2f}"


def _render_builder_attempt_history(state: dict[str, Any]) -> None:
    attempts = list(state.get("builder_attempts") or [])
    if not attempts:
        return

    current_signature = build_market_signature(state["market_data"], state.get("market_query"))
    attempt_ids = [str(item["id"]) for item in reversed(attempts)]
    selected_attempt_id = state.get("builder_selected_attempt_id")
    if selected_attempt_id not in attempt_ids:
        selected_attempt_id = attempt_ids[0]

    attempt_lookup = {str(item["id"]): item for item in attempts}
    summary_cols = st.columns([3.6, 1.0, 1.0])
    with summary_cols[0]:
        selected_attempt_id = st.selectbox(
            "Tentativa para visualizar",
            options=attempt_ids,
            index=attempt_ids.index(selected_attempt_id),
            format_func=lambda value: str(attempt_lookup[value]["selection_label"]),
        )
    state["builder_selected_attempt_id"] = selected_attempt_id

    selected_attempt = attempt_lookup[selected_attempt_id]
    summary_cols[1].metric("Tentativas", len(attempts))
    summary_cols[2].metric("Selecionada", f"#{int(selected_attempt['attempt_number']):02d}")

    previous_attempt = resolve_previous_attempt(attempts, selected_attempt_id)
    selected_summary = selected_attempt["summary"]
    if previous_attempt is not None:
        previous_summary = previous_attempt["summary"]
        st.caption(
            f"Comparando a tentativa #{int(selected_attempt['attempt_number']):02d} "
            f"com a tentativa #{int(previous_attempt['attempt_number']):02d}."
        )
        comparison_cols = st.columns(4)
        comparison_cols[0].metric(
            "Net profit",
            f"{float(selected_summary['net_profit']):.2f}",
            delta=_format_metric_delta(float(selected_summary["net_profit"]), float(previous_summary["net_profit"])),
        )
        comparison_cols[1].metric(
            "Profit factor",
            f"{float(selected_summary['profit_factor']):.2f}",
            delta=_format_metric_delta(
                float(selected_summary["profit_factor"]),
                float(previous_summary["profit_factor"]),
            ),
        )
        comparison_cols[2].metric(
            "Trades",
            int(selected_summary["total_trades"]),
            delta=int(selected_summary["total_trades"]) - int(previous_summary["total_trades"]),
        )
        comparison_cols[3].metric(
            "Win rate",
            f"{float(selected_summary['win_rate']):.1f}%",
            delta=_format_metric_delta(float(selected_summary["win_rate"]), float(previous_summary["win_rate"])),
        )
    else:
        st.caption("Primeira tentativa registrada. As proximas rodadas aparecerao com comparacao automatica.")

    with st.expander("Historico resumido", expanded=len(attempts) <= 4):
        st.dataframe(build_builder_attempts_frame(attempts), use_container_width=True)

    market_data = state["market_data"]
    if dict(selected_attempt.get("market_signature") or {}) != current_signature:
        st.warning(
            "A tentativa selecionada foi gerada com outro conjunto de candles. "
            "O grafico de preco foi ocultado para evitar comparacao incorreta."
        )
        market_data = pd.DataFrame()

    st.caption(
        f"Tentativa #{int(selected_attempt['attempt_number']):02d} | "
        f"{selected_attempt['created_at']} | {selected_attempt['label']}"
    )
    _render_backtest(
        {
            "summary": selected_attempt["summary"],
            "ambiguous_entries": selected_attempt["ambiguous_entries"],
            "trades": selected_attempt["trades"],
            "performance_curve": selected_attempt["performance_curve"],
        },
        market_data,
    )

    with st.expander("JSON da tentativa selecionada", expanded=False):
        st.json(selected_attempt["payload"])


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

    action_bar = st.container(border=True)
    with action_bar:
        st.caption("Fluxo rapido: ajuste os sinais, rode o teste e compare as tentativas ate chegar num resultado aceitavel.")
        button_col_1, button_col_2, button_col_3, button_col_4, button_col_5 = st.columns(5)
        save_clicked = button_col_1.button("💾 Salvar Estrutura", use_container_width=True)
        persist_strategy_clicked = button_col_2.button("☁️ Salvar no Backend", use_container_width=True)
        test_clicked = button_col_3.button(
            "🧪 Testar Estrategia",
            use_container_width=True,
            disabled=state["market_data"].empty,
        )
        persist_backtest_clicked = button_col_4.button(
            "🗂️ Persistir Backtest",
            use_container_width=True,
            disabled=state["market_data"].empty,
        )
        show_clicked = button_col_5.button("📄 Exibir JSON", use_container_width=True)

    if not (save_clicked or persist_strategy_clicked or test_clicked or persist_backtest_clicked or show_clicked):
        _render_builder_attempt_history(state)
        if state.get("selected_backtest_run_id"):
            if st.button("📈 Abrir detalhe da estrategia persistida", key="open-persisted-builder-run", use_container_width=True):
                state["ui_page"] = "Detalhe da Estrategia"
                st.rerun()
        return

    payload = _build_builder_payload(
        market_config=market_config,
        operation_config=operation_config,
        time_config=time_config,
        initial_setup_config=initial_setup_config,
        stop_loss_config=stop_loss_config,
        take_profit_config=take_profit_config,
        risk_config=risk_config,
        execution_config=execution_config,
        filter_config=filter_config,
        signal_config=signal_config,
        final_adjustments_config=final_adjustments_config,
    )
    state["builder_last_payload"] = payload

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

    if test_clicked:
        with st.spinner("Executando backtest simples..."):
            backtest_result = run_backtest(payload, state["market_data"])
        attempt = _store_builder_attempt(
            state=state,
            payload=payload,
            signal_config=signal_config,
            backtest_result=backtest_result,
        )
        st.success(
            "Tentativa registrada. "
            f"Trades: {int(attempt['summary']['total_trades'])} | "
            f"Net: {float(attempt['summary']['net_profit']):.2f} | "
            f"PF: {float(attempt['summary']['profit_factor']):.2f}"
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
        _store_builder_attempt(
            state=state,
            payload=payload,
            signal_config=signal_config,
            backtest_result=execution["result"],
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

    if show_clicked:
        st.json(payload)

    _render_builder_attempt_history(state)
    if state.get("selected_backtest_run_id"):
        if st.button("📈 Abrir detalhe da estrategia persistida", key="open-persisted-builder-run", use_container_width=True):
            state["ui_page"] = "Detalhe da Estrategia"
            st.rerun()


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
