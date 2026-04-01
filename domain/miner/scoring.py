from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log1p
from typing import Any

import pandas as pd

from domain.miner.space import MinerFilterConfig


@dataclass(slots=True)
class BacktestMetricSnapshot:
    total_trades: int
    net_profit: float
    max_drawdown: float
    profit_factor: float
    expectancy: float
    average_return_per_trade: float
    pnl_variance: float
    stability: float


@dataclass(slots=True)
class ScoreBreakdown:
    score: float
    mode: str
    profit_factor: float
    stability: float
    expectancy: float
    average_return_per_trade: float
    pnl_variance: float
    trade_count_factor: float
    drawdown_penalty: float
    consistency: float
    overfit_penalty: float
    temporal_stability: float
    passed_filters: bool
    rejection_reason: str | None
    train_metrics: BacktestMetricSnapshot | None = None
    test_metrics: BacktestMetricSnapshot | None = None


def compute_profit_factor(summary: dict[str, Any]) -> float:
    provided = summary.get("profit_factor")
    if provided is not None:
        value = float(provided)
        if isfinite(value):
            return value

    gross_profit = float(summary.get("gross_profit", 0.0))
    gross_loss = abs(float(summary.get("gross_loss", 0.0)))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def compute_stability(backtest_result: dict[str, Any]) -> float:
    trades = backtest_result["trades"]
    if trades.empty:
        return 0.0

    pnl = trades["pnl"].astype(float)
    avg_abs = abs(float(pnl.mean())) + 1e-9
    volatility_ratio = float(pnl.std(ddof=0)) / avg_abs if len(pnl) > 1 else 0.0
    smoothness = 1.0 / (1.0 + max(volatility_ratio, 0.0))
    win_rate = float(backtest_result["summary"].get("win_rate", 0.0)) / 100.0

    temporal_consistency = 1.0
    if "performance_curve" in backtest_result:
        curve = backtest_result["performance_curve"]
        if isinstance(curve, pd.DataFrame) and len(curve) > 2:
            increments = curve["equity"].astype(float).diff().fillna(0.0)
            sign_changes = int(((increments > 0) != (increments.shift(1) > 0)).sum())
            temporal_consistency = 1.0 / (1.0 + max(sign_changes - 1, 0))

    return max(0.0, min(1.0, (smoothness * 0.45) + (win_rate * 0.30) + (temporal_consistency * 0.25)))


def summarize_backtest_metrics(backtest_result: dict[str, Any]) -> BacktestMetricSnapshot:
    summary = backtest_result["summary"]
    return BacktestMetricSnapshot(
        total_trades=int(summary.get("total_trades", 0)),
        net_profit=float(summary.get("net_profit", 0.0)),
        max_drawdown=abs(float(summary.get("max_drawdown", 0.0))),
        profit_factor=compute_profit_factor(summary),
        expectancy=float(summary.get("expectancy", summary.get("average_pnl", 0.0))),
        average_return_per_trade=float(summary.get("average_return_per_trade", summary.get("average_pnl", 0.0))),
        pnl_variance=float(summary.get("pnl_variance", 0.0)),
        stability=compute_stability(backtest_result),
    )


def _bounded_profit_factor(value: float, floor: float) -> float:
    if not isfinite(value):
        return 1.5
    return min(value / max(floor * 2, 1e-9), 1.5)


def _variance_penalty(variance: float) -> float:
    return 1.0 / (1.0 + log1p(max(variance, 0.0)))


def _relative_gap(left: float, right: float) -> float:
    scale = max(abs(left), abs(right), 1.0)
    return abs(left - right) / scale


def _pair_consistency(train: BacktestMetricSnapshot, test: BacktestMetricSnapshot) -> float:
    profit_gap = _relative_gap(train.net_profit, test.net_profit)
    expectancy_gap = _relative_gap(train.expectancy, test.expectancy)
    variance_gap = _relative_gap(train.pnl_variance, test.pnl_variance)
    trade_balance = min(train.total_trades, test.total_trades) / max(train.total_trades, test.total_trades, 1)

    finite_train_pf = train.profit_factor if isfinite(train.profit_factor) else max(test.profit_factor, 1.0)
    finite_test_pf = test.profit_factor if isfinite(test.profit_factor) else max(train.profit_factor, 1.0)
    profit_factor_gap = _relative_gap(finite_train_pf, finite_test_pf)

    consistency = 1.0 - (
        (profit_gap * 0.35)
        + (profit_factor_gap * 0.20)
        + (expectancy_gap * 0.20)
        + (variance_gap * 0.10)
        + ((1.0 - trade_balance) * 0.15)
    )
    return max(0.0, min(1.0, consistency))


def _overfit_penalty(train: BacktestMetricSnapshot, test: BacktestMetricSnapshot) -> float:
    if train.net_profit <= 0.0 or test.net_profit <= 0.0:
        return 0.0

    profit_ratio = min(test.net_profit / max(train.net_profit, 1e-9), 1.0)
    expectancy_ratio = min(
        max(test.expectancy, 0.0) / max(max(train.expectancy, 0.0), 1e-9),
        1.0,
    )
    stability_ratio = min(test.stability / max(train.stability, 1e-9), 1.0) if train.stability > 0 else test.stability
    return max(0.0, min(1.0, (profit_ratio * 0.45) + (expectancy_ratio * 0.30) + (stability_ratio * 0.25)))


def passes_filters(
    summary: dict[str, Any],
    filters: MinerFilterConfig,
    *,
    stage: str | None = None,
) -> tuple[bool, str | None]:
    total_trades = int(summary.get("total_trades", 0))
    net_profit = float(summary.get("net_profit", 0.0))
    max_drawdown = abs(float(summary.get("max_drawdown", 0.0)))
    profit_factor = compute_profit_factor(summary)

    prefix = f"{stage}:" if stage else ""
    if total_trades < filters.min_trades:
        return False, f"{prefix}min_trades"
    if net_profit <= filters.min_net_profit:
        return False, f"{prefix}net_profit"
    if max_drawdown > filters.max_drawdown:
        return False, f"{prefix}max_drawdown"
    if profit_factor < filters.min_profit_factor:
        return False, f"{prefix}profit_factor"
    return True, None


def score_backtest_result(backtest_result: dict[str, Any], filters: MinerFilterConfig) -> ScoreBreakdown:
    summary = backtest_result["summary"]
    metrics = summarize_backtest_metrics(backtest_result)
    passed_filters, rejection_reason = passes_filters(summary, filters)

    trade_count_factor = min(metrics.total_trades / max(filters.min_trades * 2, 1), 1.0)
    drawdown_penalty = 1.0 / (1.0 + log1p(metrics.max_drawdown))
    profit_component = log1p(max(metrics.net_profit, 0.0))
    expectancy_component = log1p(max(metrics.expectancy, 0.0))
    profit_factor_component = _bounded_profit_factor(metrics.profit_factor, filters.min_profit_factor)
    variance_penalty = _variance_penalty(metrics.pnl_variance)

    raw_score = (
        (profit_component * 0.30)
        + (drawdown_penalty * 0.18)
        + (metrics.stability * 0.18)
        + (trade_count_factor * 0.10)
        + (profit_factor_component * 0.10)
        + (expectancy_component * 0.06)
        + (variance_penalty * 0.08)
    )

    return ScoreBreakdown(
        score=round(raw_score * 100, 4),
        mode="simple",
        profit_factor=metrics.profit_factor,
        stability=metrics.stability,
        expectancy=metrics.expectancy,
        average_return_per_trade=metrics.average_return_per_trade,
        pnl_variance=metrics.pnl_variance,
        trade_count_factor=trade_count_factor,
        drawdown_penalty=drawdown_penalty,
        consistency=1.0,
        overfit_penalty=1.0,
        temporal_stability=metrics.stability,
        passed_filters=passed_filters,
        rejection_reason=rejection_reason,
        train_metrics=metrics,
    )


def score_train_test_results(
    train_result: dict[str, Any],
    test_result: dict[str, Any],
    filters: MinerFilterConfig,
) -> ScoreBreakdown:
    train_summary = train_result["summary"]
    test_summary = test_result["summary"]
    train_metrics = summarize_backtest_metrics(train_result)
    test_metrics = summarize_backtest_metrics(test_result)

    train_ok, train_reason = passes_filters(train_summary, filters, stage="train")
    test_ok, test_reason = passes_filters(test_summary, filters, stage="test")
    passed_filters = train_ok and test_ok
    rejection_reason = train_reason if not train_ok else test_reason

    trade_count_factor = min(
        (train_metrics.total_trades + test_metrics.total_trades) / max(filters.min_trades * 4, 1),
        1.0,
    )
    worst_drawdown = max(train_metrics.max_drawdown, test_metrics.max_drawdown)
    drawdown_penalty = 1.0 / (1.0 + log1p(worst_drawdown))
    consistency = _pair_consistency(train_metrics, test_metrics)
    overfit_penalty = _overfit_penalty(train_metrics, test_metrics)
    temporal_stability = (
        (train_metrics.stability * 0.40)
        + (test_metrics.stability * 0.40)
        + (consistency * 0.20)
    )

    train_profit_component = log1p(max(train_metrics.net_profit, 0.0))
    test_profit_component = log1p(max(test_metrics.net_profit, 0.0))
    expectancy_component = log1p(max((train_metrics.expectancy + test_metrics.expectancy) / 2.0, 0.0))
    profit_factor_component = (
        _bounded_profit_factor(train_metrics.profit_factor, filters.min_profit_factor) * 0.40
        + _bounded_profit_factor(test_metrics.profit_factor, filters.min_profit_factor) * 0.60
    )
    variance_penalty = (
        (_variance_penalty(train_metrics.pnl_variance) * 0.40)
        + (_variance_penalty(test_metrics.pnl_variance) * 0.60)
    )

    raw_score = (
        (train_profit_component * 0.10)
        + (test_profit_component * 0.20)
        + (drawdown_penalty * 0.12)
        + (profit_factor_component * 0.10)
        + (expectancy_component * 0.08)
        + (trade_count_factor * 0.08)
        + (temporal_stability * 0.12)
        + (consistency * 0.10)
        + (overfit_penalty * 0.10)
        + (variance_penalty * 0.10)
    )

    final_score = raw_score * max(consistency, 0.1) * max(overfit_penalty, 0.1)

    return ScoreBreakdown(
        score=round(final_score * 100, 4),
        mode="robust",
        profit_factor=min(train_metrics.profit_factor, test_metrics.profit_factor),
        stability=(train_metrics.stability + test_metrics.stability) / 2.0,
        expectancy=(train_metrics.expectancy + test_metrics.expectancy) / 2.0,
        average_return_per_trade=(
            train_metrics.average_return_per_trade + test_metrics.average_return_per_trade
        )
        / 2.0,
        pnl_variance=max(train_metrics.pnl_variance, test_metrics.pnl_variance),
        trade_count_factor=trade_count_factor,
        drawdown_penalty=drawdown_penalty,
        consistency=consistency,
        overfit_penalty=overfit_penalty,
        temporal_stability=temporal_stability,
        passed_filters=passed_filters,
        rejection_reason=rejection_reason,
        train_metrics=train_metrics,
        test_metrics=test_metrics,
    )
