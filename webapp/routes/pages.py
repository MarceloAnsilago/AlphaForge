from __future__ import annotations

from typing import Any

import pandas as pd
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from domain.miner.space import MinerEvaluationConfig, MinerFilterConfig
from ui.mining_helpers import build_equity_curve_frame, build_walk_forward_frame, summarize_strategy_rules
from webapp.backend import get_web_backend_context
from webapp.routes.shared import (
    build_equity_chart,
    build_walk_forward_chart,
    frame_columns,
    frame_to_records,
    json_pretty,
)
from webapp.runtime_state import get_runtime_state


bp = Blueprint("pages", __name__)


@bp.route("/campaigns", methods=["GET", "POST"])
def campaigns_page() -> Any:
    backend = get_web_backend_context()
    state = get_runtime_state()

    if request.method == "POST":
        campaign_id = _handle_campaign_creation(backend, state)
        if campaign_id is not None:
            return redirect(url_for("pages.campaign_detail_page", campaign_id=campaign_id))
        return redirect(url_for("pages.campaigns_page"))

    campaigns = backend.mining_campaign_service.list_campaigns()
    summaries = {
        item["id"]: backend.mining_campaign_service.get_campaign_summary(item["id"])
        for item in campaigns
    }
    query = request.args.get("query", "").strip().lower()
    symbol = request.args.get("symbol", "Todos")
    timeframe = request.args.get("timeframe", "Todos")

    filtered_campaigns: list[dict[str, Any]] = []
    for campaign in campaigns:
        summary = summaries.get(campaign["id"]) or {}
        if query and query not in str(campaign.get("name") or campaign.get("id") or "").lower():
            continue
        if symbol != "Todos" and str(campaign.get("symbol") or "") != symbol:
            continue
        if timeframe != "Todos" and str(campaign.get("timeframe") or "") != timeframe:
            continue
        filtered_campaigns.append({**campaign, "summary": summary})

    context = {
        "page_title": "Campanhas",
        "active_page": "pages.campaigns_page",
        "campaigns": filtered_campaigns,
        "filters": {
            "query": request.args.get("query", ""),
            "symbol": symbol,
            "timeframe": timeframe,
        },
        "filter_options": {
            "symbols": sorted({str(item.get("symbol") or "") for item in campaigns if item.get("symbol")}),
            "timeframes": sorted({str(item.get("timeframe") or "") for item in campaigns if item.get("timeframe")}),
        },
        "campaign_form_defaults": campaign_form_defaults(state),
        "builder_candle_count": (
            len(state["market_data"])
            if isinstance(state.get("market_data"), pd.DataFrame)
            else 0
        ),
    }
    template = "pages/_campaigns_content.html" if _is_htmx_request() else "pages/campaigns.html"
    return render_template(template, **context)


@bp.get("/campaigns/<campaign_id>")
def campaign_detail_page(campaign_id: str) -> Any:
    backend = get_web_backend_context()
    audit = backend.mining_campaign_service.get_campaign_audit(campaign_id)
    if audit is None:
        abort(404)

    campaign = audit["campaign"]
    summary = audit["summary"] or {}
    top_strategies = audit["top_strategies"] or []
    runs = audit["runs"] or []
    walk_forward = build_walk_forward_frame(audit["window_performance"] or [])

    return render_template(
        "pages/campaign_detail.html",
        page_title=f"Campanha {campaign.get('name', campaign_id)}",
        active_page="pages.campaigns_page",
        campaign=campaign,
        summary=summary,
        top_strategies=top_strategies,
        runs=runs,
        walk_forward_rows=frame_to_records(walk_forward),
        walk_forward_columns=frame_columns(walk_forward),
        walk_forward_chart=build_walk_forward_chart(walk_forward),
    )


@bp.get("/strategy/<run_id>")
def strategy_detail_page(run_id: str) -> Any:
    backend = get_web_backend_context()
    run = backend.backtest_repository.get_run_with_metrics(run_id)
    if run is None:
        abort(404)

    version = backend.strategy_repository.get_strategy_version(run["strategy_version_id"])
    strategy = backend.strategy_repository.get_strategy(run["strategy_id"])
    trades = backend.backtest_repository.list_backtest_trades(run_id)
    trade_frame = pd.DataFrame(trades)
    equity_curve = build_equity_curve_frame(trades)
    rules_summary = summarize_strategy_rules((version or {}).get("spec") or {})
    strategy_window_rows = build_strategy_window_rows(backend, run)
    strategy_walk_forward = build_walk_forward_frame(strategy_window_rows)

    return render_template(
        "pages/strategy_detail.html",
        page_title=f"Estrategia {run_id}",
        active_page="pages.campaigns_page",
        run=run,
        version=version,
        strategy=strategy,
        rules_summary=rules_summary,
        spec_json=json_pretty((version or {}).get("spec") or {}),
        trades_rows=frame_to_records(trade_frame),
        trades_columns=frame_columns(trade_frame),
        equity_chart=build_equity_chart(equity_curve),
        strategy_walk_forward_rows=frame_to_records(strategy_walk_forward),
        strategy_walk_forward_columns=frame_columns(strategy_walk_forward),
        strategy_walk_forward_chart=build_walk_forward_chart(strategy_walk_forward),
    )


def campaign_form_defaults(state: dict[str, Any]) -> dict[str, Any]:
    saved_strategy = state.get("saved_strategy") or {}
    saved_market = saved_strategy.get("market") or {}
    market_query = state.get("market_query") or {}
    builder_candles = state.get("market_data")
    default_source = "Builder" if isinstance(builder_candles, pd.DataFrame) and not builder_candles.empty else "CSV"
    return {
        "source_mode": default_source,
        "evaluation_mode": "simple",
        "quantity": 25,
        "top_k": 5,
        "campaign_name": "",
        "symbol": str(market_query.get("symbol") or saved_market.get("symbol") or ""),
        "timeframe": str(market_query.get("timeframe") or saved_market.get("timeframe") or ""),
        "dataset_id": "primary",
        "seed": 42,
        "max_rules_per_strategy": 2,
        "min_split_bars": 20,
        "min_trades": 5,
        "min_net_profit": 0.0,
        "max_drawdown": 1000.0,
        "min_profit_factor": 1.1,
        "train_ratio": 0.7,
        "test_ratio": 0.2,
        "min_window_pass_rate": 1.0,
        "max_windows_value": 0,
    }


def _handle_campaign_creation(backend: Any, state: dict[str, Any]) -> str | None:
    form = request.form
    try:
        candles = _resolve_campaign_candles(
            state,
            source_mode=str(form.get("source_mode", "Builder")),
            uploaded_file=request.files.get("campaign_csv"),
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        return None

    evaluation_mode = str(form.get("evaluation_mode", "simple"))
    filters = MinerFilterConfig(
        min_trades=_int(form.get("min_trades"), 5),
        min_net_profit=_float(form.get("min_net_profit"), 0.0),
        max_drawdown=_float(form.get("max_drawdown"), 1000.0),
        min_profit_factor=_float(form.get("min_profit_factor"), 1.1),
    )
    evaluation = MinerEvaluationConfig(
        mode=evaluation_mode,
        train_ratio=_float(form.get("train_ratio"), 0.7),
        test_ratio=_float(form.get("test_ratio"), 0.2),
        minimum_partition_size=_int(form.get("min_split_bars"), 20),
        minimum_window_pass_rate=_float(form.get("min_window_pass_rate"), 1.0),
        max_walk_forward_windows=_none_if_zero(_int(form.get("max_windows_value"), 0)),
        dataset_id=str(form.get("dataset_id", "primary")).strip() or "primary",
    )

    result = backend.miner_service.mine_batch(
        candles=candles,
        quantity=_int(form.get("quantity"), 25),
        symbol=str(form.get("symbol", "")).strip() or None,
        timeframe=str(form.get("timeframe", "")).strip() or None,
        seed=_int(form.get("seed"), 42),
        top_k=_int(form.get("top_k"), 5),
        max_rules_per_strategy=_int(form.get("max_rules_per_strategy"), 2),
        filters=filters,
        evaluation=evaluation,
        campaign_name=str(form.get("campaign_name", "")).strip() or None,
    )
    campaign = result["campaign"]
    state["selected_campaign_id"] = campaign["id"]
    flash(
        "Campanha concluida. "
        f"Processadas: {result['summary']['processed']} | "
        f"Aprovadas: {result['summary']['accepted']} | "
        f"Top: {result['summary']['top_ranked']}",
        "success",
    )
    return str(campaign["id"])


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

    if uploaded_file is None or not getattr(uploaded_file, "filename", ""):
        raise ValueError("Envie um CSV para rodar a campanha.")

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
    candles = candles.sort_values("time").reset_index(drop=True)
    if candles.empty:
        raise ValueError("O CSV nao possui candles validos apos a normalizacao.")
    return candles.loc[:, ["time", "open", "high", "low", "close", "tick_volume"]].copy()


def build_strategy_window_rows(backend: Any, run: dict[str, Any]) -> list[dict[str, Any]]:
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


def _is_htmx_request() -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


def _none_if_zero(value: int) -> int | None:
    return None if value <= 0 else value


def _int(raw_value: Any, default: int) -> int:
    try:
        return int(str(raw_value))
    except (TypeError, ValueError):
        return default


def _float(raw_value: Any, default: float) -> float:
    try:
        return float(str(raw_value))
    except (TypeError, ValueError):
        return default
