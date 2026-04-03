from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from domain.miner.space import MinerEvaluationConfig, MinerFilterConfig
from ui.backend import UiBackendContext
from ui.mining_helpers import (
    build_equity_curve_frame,
    build_walk_forward_frame,
    filter_campaign_rows,
    filter_strategy_rows,
    paginate_rows,
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

            .top-strategy-card {
                border: 1px solid #cbd8ea;
                border-radius: 18px;
                padding: 1rem 1.05rem;
                background: linear-gradient(160deg, #fefefe, #eef6ff);
                min-height: 160px;
            }

            .top-strategy-rank {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.2rem 0.6rem;
                background: #123a6b;
                color: #ffffff;
                font-size: 0.78rem;
                font-weight: 700;
                margin-bottom: 0.7rem;
            }

            .top-strategy-name {
                font-size: 1rem;
                font-weight: 700;
                color: #10233d;
                margin-bottom: 0.35rem;
            }

            .top-strategy-meta {
                font-size: 0.83rem;
                color: #5b6f87;
                margin-bottom: 0.85rem;
            }

            .nav-strip {
                border: 1px solid #dbe4f0;
                border-radius: 16px;
                padding: 0.8rem 0.95rem;
                background: #fbfdff;
                margin-bottom: 1rem;
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
    elif backend.backend_mode == "file":
        st.sidebar.info(backend.backend_status)
    else:
        st.sidebar.warning(backend.backend_status)


def render_campaigns_page(backend: UiBackendContext, state: dict[str, Any]) -> None:
    st.title("Campanhas")
    _render_campaign_creation_form(backend, state)
    campaigns = backend.mining_campaign_service.list_campaigns()
    if not campaigns:
        st.info("Nenhuma campanha encontrada no backend configurado.")
        return

    summaries = {
        item["id"]: backend.mining_campaign_service.get_campaign_summary(item["id"])
        for item in campaigns
    }
    filtered_campaigns = _render_campaign_filters(campaigns, summaries)

    total_campaigns = len(filtered_campaigns)
    completed_campaigns = sum(1 for item in filtered_campaigns if item.get("status") == "completed")
    total_approved = sum(int((item.get("summary") or {}).get("approved_quantity", 0)) for item in filtered_campaigns)
    avg_stability = _mean_or_zero(
        float((item.get("summary") or {}).get("average_stability", 0.0)) for item in filtered_campaigns
    )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Campanhas", total_campaigns)
    metric_cols[1].metric("Concluidas", completed_campaigns)
    metric_cols[2].metric("Aprovadas", total_approved)
    metric_cols[3].metric("Estabilidade media", f"{avg_stability:.2f}")

    pagination = _render_pagination_controls(
        state=state,
        prefix="campaigns",
        total_items=len(filtered_campaigns),
        default_page_size=8,
        label="campanhas",
    )
    page_data = paginate_rows(
        filtered_campaigns,
        page=pagination["page"],
        page_size=pagination["page_size"],
    )
    _sync_pagination_state(state, "campaigns", page_data)

    if not page_data["items"]:
        st.info("Nenhuma campanha atende aos filtros atuais.")
        return

    for campaign in page_data["items"]:
        summary = campaign.get("summary") or {}
        cols = st.columns([4.5, 1.2, 1.1, 1.1, 1.1, 1.35])
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
        if cols[5].button("Abrir campanha", key=f"campaign-detail-{campaign['id']}", use_container_width=True):
            state["selected_campaign_id"] = campaign["id"]
            state["ui_page"] = "Detalhe da Campanha"
            st.rerun()

    _render_pagination_summary(page_data, item_label="campanhas")


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

    nav_cols = st.columns([1.4, 1.2, 4.0])
    if nav_cols[0].button("Voltar para campanhas", use_container_width=True):
        state["ui_page"] = "Campanhas"
        st.rerun()
    if nav_cols[1].button("Recarregar", use_container_width=True):
        st.rerun()

    metric_cols = st.columns(6)
    metric_cols[0].metric("Geradas", int(summary.get("generated_quantity", campaign.get("quantity", 0))))
    metric_cols[1].metric("Deduplicadas", int(summary.get("deduplicated_quantity", 0)))
    metric_cols[2].metric("Aprovadas", int(summary.get("approved_quantity", 0)))
    metric_cols[3].metric("Pass rate", f"{float(summary.get('average_pass_rate', 0.0)):.2f}")
    metric_cols[4].metric("Estabilidade", f"{float(summary.get('average_stability', 0.0)):.2f}")
    metric_cols[5].metric("Runs finais", int(summary.get("final_run_count", 0)))

    st.subheader("Top estrategias")
    top_n = st.slider("Destaque Top N", min_value=3, max_value=max(len(top_strategies), 3), value=min(5, max(len(top_strategies), 3)))
    _render_top_strategy_cards(top_strategies[:top_n], state)

    st.subheader("Ranking completo")
    filtered_rows = _render_strategy_filters(top_strategies)
    _sync_strategy_navigation_state(state, filtered_rows)
    pagination = _render_pagination_controls(
        state=state,
        prefix="campaign_strategies",
        total_items=len(filtered_rows),
        default_page_size=10,
        label="estrategias",
    )
    page_data = paginate_rows(
        filtered_rows,
        page=pagination["page"],
        page_size=pagination["page_size"],
    )
    _sync_pagination_state(state, "campaign_strategies", page_data)

    if not page_data["items"]:
        st.info("Nenhuma estrategia atende aos filtros atuais.")
    else:
        for rank_offset, row in enumerate(page_data["items"], start=page_data["start_index"] + 1):
            cols = st.columns([0.9, 2.8, 1.0, 1.0, 1.1, 1.1, 1.55])
            cols[0].markdown(f"**#{row.get('top_rank') or rank_offset}**")
            cols[1].markdown(
                f"**{row.get('strategy_name') or row.get('strategy_id')}**  \n"
                f"`{row.get('strategy_direction') or '-'}` | v{row.get('version_number') or '-'}"
            )
            cols[2].metric("Score", f"{float(row.get('score') or 0.0):.2f}")
            cols[3].metric("Status", str(row.get("status") or "-"))
            metrics = row.get("metrics") or {}
            cols[4].metric("PnL", f"{float(metrics.get('net_profit', 0.0)):.2f}")
            cols[5].metric("PF", f"{float(metrics.get('profit_factor', 0.0)):.2f}")
            if cols[6].button("Abrir estrategia", key=f"open-strategy-{row['backtest_run_id']}", use_container_width=True):
                _select_strategy(state, filtered_rows, row["backtest_run_id"], row.get("strategy_version_id"), campaign["id"])
                st.rerun()

        _render_pagination_summary(page_data, item_label="estrategias")

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

    _render_strategy_navigation_strip(state, run)

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
        render_equity_curve_section(equity_curve)

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
    chart_frame["pass_rate_pct"] = chart_frame["pass_rate"].fillna(0.0) * 100.0

    score_bars = (
        alt.Chart(chart_frame)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X("window_label:N", title="Janela"),
            y=alt.Y("average_score:Q", title="Score medio"),
            color=alt.Color("dataset_role:N", title="Role"),
            tooltip=[
                alt.Tooltip("window_label:N", title="Janela"),
                alt.Tooltip("dataset_role:N", title="Role"),
                alt.Tooltip("average_score:Q", title="Score", format=".2f"),
                alt.Tooltip("pass_rate_pct:Q", title="Pass rate %", format=".1f"),
                alt.Tooltip("average_stability:Q", title="Estabilidade", format=".2f"),
            ],
        )
    )
    stability_line = (
        alt.Chart(chart_frame)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("window_label:N", title="Janela"),
            y=alt.Y("average_stability:Q", title="Estabilidade media"),
            color=alt.Color("dataset_role:N", title="Role"),
            tooltip=[
                alt.Tooltip("window_label:N", title="Janela"),
                alt.Tooltip("dataset_role:N", title="Role"),
                alt.Tooltip("average_stability:Q", title="Estabilidade", format=".2f"),
                alt.Tooltip("pass_rate_pct:Q", title="Pass rate %", format=".1f"),
            ],
        )
    )
    pass_rate_line = (
        alt.Chart(chart_frame)
        .mark_line(point=True, strokeDash=[6, 3], strokeWidth=2)
        .encode(
            x=alt.X("window_label:N", title="Janela"),
            y=alt.Y("pass_rate_pct:Q", title="Pass rate %"),
            color=alt.Color("dataset_role:N", title="Role"),
            tooltip=[
                alt.Tooltip("window_label:N", title="Janela"),
                alt.Tooltip("dataset_role:N", title="Role"),
                alt.Tooltip("pass_rate_pct:Q", title="Pass rate %", format=".1f"),
            ],
        )
    )

    chart_cols = st.columns(2)
    chart_cols[0].altair_chart(score_bars.properties(height=300), use_container_width=True)
    chart_cols[1].altair_chart((stability_line + pass_rate_line).properties(height=300), use_container_width=True)
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


def render_equity_curve_section(equity_curve: pd.DataFrame) -> None:
    curve = equity_curve.copy()
    curve["time_label"] = curve["time"].astype(str)

    equity_chart = (
        alt.Chart(curve)
        .mark_line(color="#0f766e", strokeWidth=3)
        .encode(
            x=alt.X("time:T", title="Tempo"),
            y=alt.Y("equity:Q", title="Equity"),
            tooltip=[
                alt.Tooltip("trade_number:Q", title="Trade"),
                alt.Tooltip("equity:Q", title="Equity", format=".2f"),
                alt.Tooltip("pnl:Q", title="PnL", format=".2f"),
                alt.Tooltip("drawdown:Q", title="Drawdown", format=".2f"),
            ],
        )
        .properties(height=320)
    )
    pnl_bars = (
        alt.Chart(curve)
        .mark_bar(opacity=0.8)
        .encode(
            x=alt.X("time:T", title="Tempo"),
            y=alt.Y("pnl:Q", title="PnL por trade"),
            color=alt.condition("datum.pnl >= 0", alt.value("#16a34a"), alt.value("#dc2626")),
            tooltip=[
                alt.Tooltip("trade_number:Q", title="Trade"),
                alt.Tooltip("pnl:Q", title="PnL", format=".2f"),
                alt.Tooltip("equity:Q", title="Equity", format=".2f"),
            ],
        )
        .properties(height=320)
    )
    drawdown_area = (
        alt.Chart(curve)
        .mark_area(color="#f59e0b", opacity=0.35)
        .encode(
            x=alt.X("time:T", title="Tempo"),
            y=alt.Y("drawdown:Q", title="Drawdown"),
            tooltip=[
                alt.Tooltip("trade_number:Q", title="Trade"),
                alt.Tooltip("drawdown:Q", title="Drawdown", format=".2f"),
            ],
        )
        .properties(height=160)
    )

    chart_cols = st.columns(2)
    chart_cols[0].altair_chart(equity_chart, use_container_width=True)
    chart_cols[1].altair_chart(pnl_bars, use_container_width=True)
    st.altair_chart(drawdown_area, use_container_width=True)


def _render_campaign_creation_form(backend: UiBackendContext, state: dict[str, Any]) -> None:
    saved_strategy = state.get("saved_strategy") or {}
    saved_market = saved_strategy.get("market") or {}
    market_query = state.get("market_query") or {}
    builder_candles = state.get("market_data")
    default_symbol = str(market_query.get("symbol") or saved_market.get("symbol") or "")
    default_timeframe = str(market_query.get("timeframe") or saved_market.get("timeframe") or "")
    default_source = "Builder" if isinstance(builder_candles, pd.DataFrame) and not builder_candles.empty else "CSV"

    with st.expander("Executar nova campanha", expanded=False):
        st.caption("Use os candles do builder ou envie um CSV para rodar o minerador pela interface.")
        with st.form("run_mining_campaign_form"):
            source_col, mode_col, quantity_col, topk_col = st.columns(4)
            source_mode = source_col.selectbox("Origem dos candles", options=["Builder", "CSV"], index=["Builder", "CSV"].index(default_source))
            evaluation_mode = mode_col.selectbox(
                "Modo de avaliacao",
                options=["simple", "robust", "robust_walk_forward"],
                index=0,
            )
            quantity = int(quantity_col.number_input("Quantidade", min_value=1, value=25, step=1))
            top_k = int(topk_col.number_input("Top K", min_value=0, value=5, step=1))

            meta_col_1, meta_col_2, meta_col_3, meta_col_4 = st.columns(4)
            campaign_name = meta_col_1.text_input("Nome da campanha", value="")
            symbol = meta_col_2.text_input("Simbolo", value=default_symbol)
            timeframe = meta_col_3.text_input("Timeframe", value=default_timeframe)
            dataset_id = meta_col_4.text_input("Dataset ID", value="primary")

            run_col_1, run_col_2, run_col_3 = st.columns(3)
            seed = int(run_col_1.number_input("Seed", min_value=0, value=42, step=1))
            max_rules_per_strategy = int(run_col_2.number_input("Max regras/estrategia", min_value=1, value=2, step=1))
            min_split_bars = int(run_col_3.number_input("Min candles por particao", min_value=5, value=20, step=1))

            filter_cols = st.columns(4)
            min_trades = int(filter_cols[0].number_input("Min trades", min_value=0, value=5, step=1))
            min_net_profit = float(filter_cols[1].number_input("Min net profit", value=0.0, step=1.0, format="%.2f"))
            max_drawdown = float(filter_cols[2].number_input("Max drawdown", min_value=0.0, value=1000.0, step=10.0, format="%.2f"))
            min_profit_factor = float(filter_cols[3].number_input("Min profit factor", min_value=0.0, value=1.1, step=0.1, format="%.2f"))

            train_ratio = 0.7
            test_ratio = 0.2
            min_window_pass_rate = 1.0
            max_windows_value = 0
            if evaluation_mode in {"robust", "robust_walk_forward"}:
                robust_cols = st.columns(4)
                train_ratio = float(robust_cols[0].slider("Train ratio", min_value=0.1, max_value=0.9, value=0.7, step=0.05))
                test_ratio = float(robust_cols[1].slider("Test ratio", min_value=0.1, max_value=0.8, value=0.2, step=0.05))
                min_window_pass_rate = float(
                    robust_cols[2].slider("Min window pass rate", min_value=0.0, max_value=1.0, value=1.0, step=0.05)
                )
                max_windows_value = int(robust_cols[3].number_input("Max windows (0 = sem limite)", min_value=0, value=0, step=1))

            uploaded_file = None
            if source_mode == "CSV":
                uploaded_file = st.file_uploader("Dataset CSV", type=["csv"], key="campaign_csv_upload")
            else:
                loaded_count = len(builder_candles) if isinstance(builder_candles, pd.DataFrame) else 0
                st.caption(f"Candles disponiveis no builder: {loaded_count}")

            submit = st.form_submit_button("Executar campanha", use_container_width=True)

        if not submit:
            return

        try:
            candles = _resolve_campaign_candles(state, source_mode=source_mode, uploaded_file=uploaded_file)
        except ValueError as exc:
            st.error(str(exc))
            return

        filters = MinerFilterConfig(
            min_trades=min_trades,
            min_net_profit=min_net_profit,
            max_drawdown=max_drawdown,
            min_profit_factor=min_profit_factor,
        )
        evaluation = MinerEvaluationConfig(
            mode=evaluation_mode,
            train_ratio=train_ratio,
            test_ratio=test_ratio,
            minimum_partition_size=min_split_bars,
            minimum_window_pass_rate=min_window_pass_rate,
            max_walk_forward_windows=max_windows_value or None,
            dataset_id=dataset_id.strip() or "primary",
        )

        with st.spinner("Executando campanha de mineracao..."):
            result = backend.miner_service.mine_batch(
                candles=candles,
                quantity=quantity,
                symbol=symbol.strip() or None,
                timeframe=timeframe.strip() or None,
                seed=seed,
                top_k=top_k,
                max_rules_per_strategy=max_rules_per_strategy,
                filters=filters,
                evaluation=evaluation,
                campaign_name=campaign_name.strip() or None,
            )

        campaign = result["campaign"]
        state["selected_campaign_id"] = campaign["id"]
        st.success(
            "Campanha concluida. "
            f"Processadas: {result['summary']['processed']} | "
            f"Aprovadas: {result['summary']['accepted']} | "
            f"Top: {result['summary']['top_ranked']}"
        )
        if st.button("Abrir campanha criada", key=f"open-created-campaign-{campaign['id']}", use_container_width=True):
            state["ui_page"] = "Detalhe da Campanha"
            st.rerun()


def _render_campaign_filters(
    campaigns: list[dict[str, Any]],
    summaries: dict[str, dict[str, Any] | None],
) -> list[dict[str, Any]]:
    symbols = sorted({str(item.get("symbol") or "") for item in campaigns if item.get("symbol")})
    timeframes = sorted({str(item.get("timeframe") or "") for item in campaigns if item.get("timeframe")})
    filter_cols = st.columns(3)
    query = filter_cols[0].text_input("Buscar campanha", key="campaign_filter_query")
    symbol = filter_cols[1].selectbox("Simbolo", options=["Todos", *symbols], key="campaign_filter_symbol")
    timeframe = filter_cols[2].selectbox("Timeframe", options=["Todos", *timeframes], key="campaign_filter_timeframe")
    return filter_campaign_rows(
        campaigns,
        summaries,
        query=query,
        symbol=symbol,
        timeframe=timeframe,
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
    query = filter_cols[0].text_input("Buscar estrategia", key="strategy_filter_query")
    direction = filter_cols[1].selectbox("Direcao", options=["Todos", *available_directions], key="strategy_filter_direction")
    status = filter_cols[2].selectbox("Status", options=["Todos", *available_statuses], key="strategy_filter_status")
    if minimum_score != maximum_score:
        score_threshold = filter_cols[3].slider(
            "Score minimo",
            min_value=float(minimum_score),
            max_value=float(maximum_score),
            value=float(minimum_score),
            key="strategy_filter_min_score",
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


def _render_top_strategy_cards(rows: list[dict[str, Any]], state: dict[str, Any]) -> None:
    if not rows:
        st.info("Nenhuma estrategia aprovada para destacar.")
        return

    columns = st.columns(min(len(rows), 5))
    for column, row in zip(columns, rows):
        metrics = row.get("metrics") or {}
        with column:
            st.markdown(
                (
                    "<div class='top-strategy-card'>"
                    f"<div class='top-strategy-rank'>TOP {row.get('top_rank') or '-'}</div>"
                    f"<div class='top-strategy-name'>{row.get('strategy_name') or row.get('strategy_id')}</div>"
                    f"<div class='top-strategy-meta'>{row.get('strategy_direction') or '-'} | "
                    f"score {float(row.get('score') or 0.0):.2f}</div>"
                    f"<div class='top-strategy-meta'>PnL {float(metrics.get('net_profit', 0.0)):.2f} | "
                    f"PF {float(metrics.get('profit_factor', 0.0)):.2f}</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            if st.button("Abrir", key=f"top-open-{row['backtest_run_id']}", use_container_width=True):
                _select_strategy(
                    state,
                    rows,
                    row["backtest_run_id"],
                    row.get("strategy_version_id"),
                    state.get("selected_campaign_id"),
                )
                st.rerun()


def _render_strategy_navigation_strip(state: dict[str, Any], run: dict[str, Any]) -> None:
    selected_ids = list(state.get("selected_strategy_run_ids") or [])
    selected_run_id = str(run["id"])
    if selected_run_id not in selected_ids:
        selected_ids = [selected_run_id]
        state["selected_strategy_run_ids"] = selected_ids
        state["selected_strategy_position"] = 0

    position = selected_ids.index(selected_run_id)
    state["selected_strategy_position"] = position
    previous_run_id = selected_ids[position - 1] if position > 0 else None
    next_run_id = selected_ids[position + 1] if position < len(selected_ids) - 1 else None

    st.markdown("<div class='nav-strip'>", unsafe_allow_html=True)
    nav_cols = st.columns([1.3, 1.3, 2.2, 2.2])
    if nav_cols[0].button("Estrategia anterior", disabled=previous_run_id is None, use_container_width=True):
        state["selected_backtest_run_id"] = previous_run_id
        state["selected_strategy_position"] = max(position - 1, 0)
        st.rerun()
    if nav_cols[1].button("Proxima estrategia", disabled=next_run_id is None, use_container_width=True):
        state["selected_backtest_run_id"] = next_run_id
        state["selected_strategy_position"] = min(position + 1, len(selected_ids) - 1)
        st.rerun()
    nav_cols[2].metric("Posicao no ranking", f"{position + 1}/{len(selected_ids)}")
    nav_cols[3].metric("Campanha", str(run.get("campaign_id") or "-"))
    st.markdown("</div>", unsafe_allow_html=True)


def _render_pagination_controls(
    *,
    state: dict[str, Any],
    prefix: str,
    total_items: int,
    default_page_size: int,
    label: str,
) -> dict[str, Any]:
    page_key = f"{prefix}_page"
    page_size_key = f"{prefix}_page_size"
    page_size_options = [5, 8, 10, 20, 50]
    if page_key not in state:
        state[page_key] = 1
    if page_size_key not in state:
        state[page_size_key] = default_page_size
    elif int(state[page_size_key]) not in page_size_options:
        state[page_size_key] = default_page_size

    controls = st.columns([1.1, 1.1, 1.2, 3.0])
    if controls[0].button("Anterior", key=f"{prefix}_prev", disabled=state[page_key] <= 1, use_container_width=True):
        state[page_key] = max(int(state[page_key]) - 1, 1)
    if controls[1].button("Proxima", key=f"{prefix}_next", disabled=(int(state[page_key]) * int(state[page_size_key])) >= total_items, use_container_width=True):
        state[page_key] = int(state[page_key]) + 1
    controls[2].selectbox(
        f"{label} por pagina",
        options=page_size_options,
        index=page_size_options.index(int(state[page_size_key])),
        key=page_size_key,
    )
    return {
        "page": int(state[page_key]),
        "page_size": int(state[page_size_key]),
    }


def _render_pagination_summary(page_data: dict[str, Any], *, item_label: str) -> None:
    st.caption(
        f"Exibindo {page_data['start_index'] + 1 if page_data['total_items'] else 0}"
        f" a {page_data['end_index']} de {page_data['total_items']} {item_label}. "
        f"Pagina {page_data['page']} de {page_data['total_pages']}."
    )


def _sync_pagination_state(state: dict[str, Any], prefix: str, page_data: dict[str, Any]) -> None:
    state[f"{prefix}_page"] = int(page_data["page"])


def _sync_strategy_navigation_state(state: dict[str, Any], filtered_rows: list[dict[str, Any]]) -> None:
    strategy_run_ids = [str(item["backtest_run_id"]) for item in filtered_rows]
    state["selected_strategy_run_ids"] = strategy_run_ids
    selected_run_id = state.get("selected_backtest_run_id")
    if selected_run_id in strategy_run_ids:
        state["selected_strategy_position"] = strategy_run_ids.index(selected_run_id)
    elif strategy_run_ids:
        state["selected_strategy_position"] = 0


def _select_strategy(
    state: dict[str, Any],
    filtered_rows: list[dict[str, Any]],
    backtest_run_id: str,
    strategy_version_id: str | None,
    campaign_id: str | None,
) -> None:
    state["selected_campaign_id"] = campaign_id
    state["selected_backtest_run_id"] = backtest_run_id
    state["selected_strategy_version_id"] = strategy_version_id
    state["selected_strategy_run_ids"] = [str(item["backtest_run_id"]) for item in filtered_rows]
    if backtest_run_id in state["selected_strategy_run_ids"]:
        state["selected_strategy_position"] = state["selected_strategy_run_ids"].index(backtest_run_id)
    else:
        state["selected_strategy_position"] = 0
    state["ui_page"] = "Detalhe da Estrategia"


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


def _resolve_campaign_candles(
    state: dict[str, Any],
    *,
    source_mode: str,
    uploaded_file: Any,
) -> pd.DataFrame:
    if source_mode == "Builder":
        builder_candles = state.get("market_data")
        if not isinstance(builder_candles, pd.DataFrame) or builder_candles.empty:
            raise ValueError("Carregue candles no Builder antes de rodar uma campanha com essa origem.")
        return builder_candles.sort_values("time").reset_index(drop=True).copy()

    if uploaded_file is None:
        raise ValueError("Envie um CSV para rodar a campanha.")

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    candles = pd.read_csv(uploaded_file)
    required_columns = {"time", "open", "high", "low", "close"}
    missing_columns = sorted(required_columns.difference(candles.columns))
    if missing_columns:
        raise ValueError(f"CSV invalido. Colunas obrigatorias ausentes: {', '.join(missing_columns)}")
    if "tick_volume" not in candles.columns:
        candles["tick_volume"] = 0
    candles["time"] = pd.to_datetime(candles["time"], errors="coerce", utc=True)
    for column in ["open", "high", "low", "close", "tick_volume"]:
        candles[column] = pd.to_numeric(candles[column], errors="coerce")
    candles = candles.dropna(subset=["time", "open", "high", "low", "close"])
    candles = candles.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    if candles.empty:
        raise ValueError("O CSV nao possui candles validos apos a normalizacao da coluna time.")
    return candles.loc[:, ["time", "open", "high", "low", "close", "tick_volume"]].copy()
