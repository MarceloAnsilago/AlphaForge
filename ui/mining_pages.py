from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from ui.backend import UiBackendContext
from ui.mining_helpers import (
    build_equity_curve_frame,
    build_walk_forward_frame,
    filter_strategy_rows,
    summarize_strategy_rules,
)


def render_mining_pages_style() -> None:
    st.markdown(
        """
        <style>
            .campaign-card {
                border: 1px solid #dbe4f0;
                border-radius: 18px;
                padding: 1rem 1.1rem;
                background: linear-gradient(180deg, #ffffff, #f8fbff);
                margin-bottom: 0.85rem;
            }

            .campaign-card__title {
                font-size: 1.02rem;
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 0.2rem;
            }

            .campaign-card__meta {
                font-size: 0.84rem;
                color: #64748b;
            }

            .rule-box {
                border: 1px solid #e2e8f0;
                border-radius: 14px;
                padding: 0.8rem 0.95rem;
                background: #ffffff;
                margin-bottom: 0.65rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_navigation(state: dict[str, Any]) -> str:
    pages = ["Builder", "Campanhas", "Detalhe da Campanha", "Detalhe da Estrategia"]
    current_page = state.get("ui_page", "Builder")
    if current_page not in pages:
        current_page = "Builder"
    selected_page = st.sidebar.radio(
        "Navegacao",
        options=pages,
        index=pages.index(current_page),
    )
    state["ui_page"] = selected_page
    return selected_page


def render_backend_status(backend: UiBackendContext) -> None:
    if backend.backend_mode == "supabase":
        st.sidebar.success(backend.backend_status)
    else:
        st.sidebar.warning(backend.backend_status)


def render_campaigns_page(backend: UiBackendContext, state: dict[str, Any]) -> None:
    st.title("Campanhas")
    campaigns = backend.mining_campaign_service.list_campaigns()
    if not campaigns:
        st.info("Nenhuma campanha encontrada no backend configurado.")
        return

    summaries = [backend.mining_campaign_service.get_campaign_summary(item["id"]) for item in campaigns]
    total_campaigns = len(campaigns)
    completed_campaigns = sum(1 for item in campaigns if item.get("status") == "completed")
    total_approved = sum(int((summary or {}).get("approved_quantity", 0)) for summary in summaries)
    avg_stability = _mean_or_zero(float((summary or {}).get("average_stability", 0.0)) for summary in summaries)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Campanhas", total_campaigns)
    metric_cols[1].metric("Concluidas", completed_campaigns)
    metric_cols[2].metric("Aprovadas", total_approved)
    metric_cols[3].metric("Estabilidade media", f"{avg_stability:.2f}")

    for campaign, summary in zip(campaigns, summaries):
        summary = summary or {}
        cols = st.columns([4.5, 1.4, 1.2, 1.2, 1.2, 1.4])
        with cols[0]:
            st.markdown(
                (
                    "<div class='campaign-card'>"
                    f"<div class='campaign-card__title'>{campaign.get('name', campaign['id'])}</div>"
                    f"<div class='campaign-card__meta'>"
                    f"{campaign.get('evaluation_mode', 'N/A')} | "
                    f"{campaign.get('symbol') or '-'} {campaign.get('timeframe') or ''} | "
                    f"dataset {campaign.get('dataset_id', '-')}"
                    "</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
        cols[1].metric("Geradas", int(summary.get("generated_quantity", campaign.get("quantity", 0))))
        cols[2].metric("Dedup", int(summary.get("deduplicated_quantity", 0)))
        cols[3].metric("Aprovadas", int(summary.get("approved_quantity", 0)))
        cols[4].metric("Pass rate", f"{float(summary.get('average_pass_rate', 0.0)):.2f}")
        if cols[5].button("Detalhes", key=f"campaign-detail-{campaign['id']}", use_container_width=True):
            state["selected_campaign_id"] = campaign["id"]
            state["ui_page"] = "Detalhe da Campanha"
            st.rerun()


def render_campaign_detail_page(backend: UiBackendContext, state: dict[str, Any]) -> None:
    campaigns = backend.mining_campaign_service.list_campaigns()
    if not campaigns:
        st.title("Detalhe da Campanha")
        st.info("Nenhuma campanha disponivel.")
        return

    campaign_ids = [item["id"] for item in campaigns]
    selected_campaign_id = state.get("selected_campaign_id")
    if selected_campaign_id not in campaign_ids:
        selected_campaign_id = campaign_ids[0]
        state["selected_campaign_id"] = selected_campaign_id

    selected_campaign_id = st.selectbox(
        "Campanha",
        options=campaign_ids,
        index=campaign_ids.index(selected_campaign_id),
        format_func=lambda value: _campaign_label(campaigns, value),
    )
    state["selected_campaign_id"] = selected_campaign_id

    audit = backend.mining_campaign_service.get_campaign_audit(selected_campaign_id)
    if audit is None:
        st.info("Campanha nao encontrada.")
        return

    campaign = audit["campaign"]
    summary = audit["summary"] or {}
    top_strategies = audit["top_strategies"] or []
    window_performance = audit["window_performance"] or []

    st.title(f"Detalhe da Campanha: {campaign.get('name', selected_campaign_id)}")
    st.caption(
        f"Status: {campaign.get('status')} | "
        f"Modo: {campaign.get('evaluation_mode')} | "
        f"Mercado: {campaign.get('symbol') or '-'} {campaign.get('timeframe') or ''}"
    )

    metric_cols = st.columns(6)
    metric_cols[0].metric("Geradas", int(summary.get("generated_quantity", campaign.get("quantity", 0))))
    metric_cols[1].metric("Deduplicadas", int(summary.get("deduplicated_quantity", 0)))
    metric_cols[2].metric("Aprovadas", int(summary.get("approved_quantity", 0)))
    metric_cols[3].metric("Pass rate", f"{float(summary.get('average_pass_rate', 0.0)):.2f}")
    metric_cols[4].metric("Estabilidade", f"{float(summary.get('average_stability', 0.0)):.2f}")
    metric_cols[5].metric("Runs finais", int(summary.get("final_run_count", 0)))

    st.subheader("Top estrategias")
    filtered_rows = _render_strategy_filters(top_strategies)
    if not filtered_rows:
        st.info("Nenhuma estrategia atende aos filtros atuais.")
    else:
        for rank, row in enumerate(filtered_rows, start=1):
            cols = st.columns([0.8, 2.8, 1.1, 1.1, 1.1, 1.1, 1.4])
            cols[0].markdown(f"**#{row.get('top_rank') or rank}**")
            cols[1].markdown(
                f"**{row.get('strategy_name') or row.get('strategy_id')}**  \n"
                f"`{row.get('strategy_direction') or '-'}` | v{row.get('version_number') or '-'}"
            )
            cols[2].metric("Score", f"{float(row.get('score') or 0.0):.2f}")
            cols[3].metric("Status", str(row.get("status") or "-"))
            metrics = row.get("metrics") or {}
            cols[4].metric("PnL", f"{float(metrics.get('net_profit', 0.0)):.2f}")
            cols[5].metric("PF", f"{float(metrics.get('profit_factor', 0.0)):.2f}")
            if cols[6].button("Abrir", key=f"open-strategy-{row['backtest_run_id']}", use_container_width=True):
                state["selected_backtest_run_id"] = row["backtest_run_id"]
                state["selected_strategy_version_id"] = row.get("strategy_version_id")
                state["ui_page"] = "Detalhe da Estrategia"
                st.rerun()

    st.subheader("Walk-forward")
    if window_performance:
        render_walk_forward_section(window_performance)
    else:
        st.info("Esta campanha nao possui agregacao por janela disponivel.")


def render_strategy_detail_page(backend: UiBackendContext, state: dict[str, Any]) -> None:
    st.title("Detalhe da Estrategia")
    selected_run_id = state.get("selected_backtest_run_id")
    if not selected_run_id:
        st.info("Abra uma estrategia a partir do detalhe de uma campanha.")
        return

    run = backend.backtest_repository.get_run_with_metrics(selected_run_id)
    if run is None:
        st.warning("Run selecionado nao foi encontrado.")
        return

    version = backend.strategy_repository.get_strategy_version(run["strategy_version_id"])
    strategy = backend.strategy_repository.get_strategy(run["strategy_id"])
    trades = backend.backtest_repository.list_backtest_trades(selected_run_id)
    trade_frame = pd.DataFrame(trades)
    equity_curve = build_equity_curve_frame(trades)
    rules_summary = summarize_strategy_rules((version or {}).get("spec") or {})

    title_name = (version or {}).get("strategy_name") or (strategy or {}).get("name") or run["strategy_id"]
    st.caption(
        f"Run: {selected_run_id} | "
        f"Modo: {run.get('evaluation_mode')} | "
        f"Status: {run.get('status')}"
    )

    header_cols = st.columns([4, 1.2])
    header_cols[0].subheader(title_name)
    if header_cols[1].button("Voltar a campanha", use_container_width=True):
        if run.get("campaign_id"):
            state["selected_campaign_id"] = run["campaign_id"]
        state["ui_page"] = "Detalhe da Campanha"
        st.rerun()

    metric_cols = st.columns(6)
    metrics = run.get("metrics") or {}
    metric_cols[0].metric("Score", f"{float(run.get('score') or 0.0):.2f}")
    metric_cols[1].metric("Trades", int(metrics.get("total_trades", 0)))
    metric_cols[2].metric("Net profit", f"{float(metrics.get('net_profit', 0.0)):.2f}")
    metric_cols[3].metric("Profit factor", f"{float(metrics.get('profit_factor', 0.0)):.2f}")
    metric_cols[4].metric("Drawdown", f"{float(metrics.get('max_drawdown', 0.0)):.2f}")
    metric_cols[5].metric("Stability", f"{float(metrics.get('stability', 0.0)):.2f}")

    info_cols = st.columns(4)
    info_cols[0].markdown(f"**Direcao**  \n{(version or {}).get('direction') or (strategy or {}).get('direction') or '-'}")
    info_cols[1].markdown(f"**Simbolo**  \n{run.get('symbol') or '-'}")
    info_cols[2].markdown(f"**Timeframe**  \n{run.get('timeframe') or '-'}")
    info_cols[3].markdown(f"**Dataset role**  \n{run.get('dataset_role') or '-'}")

    st.subheader("Regras")
    rule_cols = st.columns(2)
    with rule_cols[0]:
        st.markdown("**Entrada**")
        for item in rules_summary["entry_rules"] or ["Nenhuma regra de entrada."]:
            st.markdown(f"<div class='rule-box'>{item}</div>", unsafe_allow_html=True)
    with rule_cols[1]:
        st.markdown("**Saida**")
        for item in rules_summary["exit_rules"] or ["Nenhuma regra de saida."]:
            st.markdown(f"<div class='rule-box'>{item}</div>", unsafe_allow_html=True)

    with st.expander("Spec completa", expanded=False):
        st.json((version or {}).get("spec") or {})

    st.subheader("Equity Curve")
    if equity_curve.empty:
        st.info("Nenhum trade encontrado para este run.")
    else:
        st.line_chart(equity_curve.set_index("time")[["equity"]], use_container_width=True)

    strategy_window_rows = _build_strategy_window_rows(backend, run)
    if strategy_window_rows:
        st.subheader("Walk-forward da estrategia")
        render_walk_forward_section(strategy_window_rows)

    st.subheader("Trades")
    if trade_frame.empty:
        st.info("Nenhum trade persistido para este run.")
    else:
        visible_columns = [
            column
            for column in ["trade_number", "side", "entry_time", "exit_time", "entry_price", "exit_price", "pnl", "holding_bars"]
            if column in trade_frame.columns
        ]
        st.dataframe(trade_frame.loc[:, visible_columns], use_container_width=True)


def render_walk_forward_section(window_rows: list[dict[str, Any]]) -> None:
    frame = build_walk_forward_frame(window_rows)
    if frame.empty:
        st.info("Nenhum dado walk-forward disponivel.")
        return

    chart_frame = frame.copy()
    chart_frame["window_label"] = chart_frame["window_label"].fillna("window_0")
    chart_frame["dataset_role"] = chart_frame["dataset_role"].fillna("full")

    score_chart = (
        alt.Chart(chart_frame)
        .mark_bar()
        .encode(
            x=alt.X("window_label:N", title="Janela"),
            y=alt.Y("average_score:Q", title="Score medio"),
            color=alt.Color("dataset_role:N", title="Role"),
            tooltip=["window_label:N", "dataset_role:N", "average_score:Q", "pass_rate:Q", "average_stability:Q"],
        )
        .properties(height=280)
    )
    stability_chart = (
        alt.Chart(chart_frame)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("window_label:N", title="Janela"),
            y=alt.Y("average_stability:Q", title="Estabilidade media"),
            color=alt.Color("dataset_role:N", title="Role"),
            tooltip=["window_label:N", "dataset_role:N", "average_stability:Q", "pass_rate:Q"],
        )
        .properties(height=280)
    )

    chart_cols = st.columns(2)
    chart_cols[0].altair_chart(score_chart, use_container_width=True)
    chart_cols[1].altair_chart(stability_chart, use_container_width=True)
    st.dataframe(
        frame.loc[
            :,
            [
                "window_index",
                "window_label",
                "dataset_role",
                "partition_origin",
                "average_score",
                "pass_rate",
                "average_stability",
                "average_net_profit",
                "average_profit_factor",
            ],
        ],
        use_container_width=True,
    )


def _render_strategy_filters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    available_scores = [float(item.get("score") or 0.0) for item in rows if item.get("score") is not None]
    minimum_score = min(available_scores) if available_scores else 0.0
    maximum_score = max(available_scores) if available_scores else 0.0
    available_directions = sorted({str(item.get("strategy_direction") or "") for item in rows if item.get("strategy_direction")})
    available_statuses = sorted({str(item.get("status") or "") for item in rows if item.get("status")})

    filter_cols = st.columns(4)
    query = filter_cols[0].text_input("Buscar", value="")
    direction = filter_cols[1].selectbox("Direcao", options=["Todos", *available_directions])
    status = filter_cols[2].selectbox("Status", options=["Todos", *available_statuses])
    if minimum_score != maximum_score:
        score_threshold = filter_cols[3].slider(
            "Score minimo",
            min_value=float(minimum_score),
            max_value=float(maximum_score),
            value=float(minimum_score),
        )
    else:
        filter_cols[3].metric("Score", f"{minimum_score:.2f}")
        score_threshold = float(minimum_score)

    return filter_strategy_rows(
        rows,
        query=query,
        direction=direction,
        status=status,
        minimum_score=score_threshold,
    )


def _build_strategy_window_rows(backend: UiBackendContext, run: dict[str, Any]) -> list[dict[str, Any]]:
    campaign_id = run.get("campaign_id")
    strategy_id = run.get("strategy_id")
    if not campaign_id or not strategy_id:
        return []
    rows = backend.mining_campaign_service.list_campaign_runs(campaign_id)
    grouped: list[dict[str, Any]] = []
    for row in rows:
        if row.get("strategy_id") != strategy_id:
            continue
        metrics = row.get("metrics") or {}
        execution_parameters = row.get("execution_parameters") or {}
        window_result = execution_parameters.get("window_result") if isinstance(execution_parameters.get("window_result"), dict) else None
        grouped.append(
            {
                "window_index": row.get("window_index"),
                "window_label": row.get("window_label"),
                "dataset_role": row.get("dataset_role"),
                "partition_origin": row.get("partition_origin"),
                "average_score": float((window_result or {}).get("score", row.get("score") or 0.0)),
                "pass_rate": 1.0 if bool((window_result or {}).get("passed_filters", row.get("passed_filters"))) else 0.0,
                "average_stability": float(metrics.get("stability", 0.0)),
                "average_net_profit": float(metrics.get("net_profit", 0.0)),
                "average_profit_factor": float(metrics.get("profit_factor", 0.0)),
            }
        )
    return sorted(grouped, key=lambda item: (int(item.get("window_index") or 0), str(item.get("dataset_role") or "")))


def _campaign_label(campaigns: list[dict[str, Any]], campaign_id: str) -> str:
    for item in campaigns:
        if item["id"] == campaign_id:
            return f"{item.get('name', campaign_id)} ({campaign_id})"
    return campaign_id


def _mean_or_zero(values: Any) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
