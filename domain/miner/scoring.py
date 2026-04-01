from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log1p
from statistics import mean, pstdev
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
class WalkForwardWindowScore:
    window_index: int
    label: str
    score: float
    passed_filters: bool
    rejection_reason: str | None
    consistency: float
    overfit_penalty: float
    temporal_stability: float
    train_metrics: BacktestMetricSnapshot
    test_metrics: BacktestMetricSnapshot


@dataclass(slots=True)
class WalkForwardAggregateMetrics:
    total_windows: int
    approved_windows: int
    window_pass_rate: float
    average_train_profit: float
    average_test_profit: float
    average_train_drawdown: float
    average_test_drawdown: float
    average_train_profit_factor: float
    average_test_profit_factor: float
    stability_between_windows: float
    dependency_penalty: float


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
    window_scores: list[WalkForwardWindowScore] | None = None
    walk_forward_metrics: WalkForwardAggregateMetrics | None = None


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


def _mean_or_zero(values: list[float]) -> float:
    return mean(values) if values else 0.0


def _series_stability(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return 1.0
    baseline = abs(_mean_or_zero(values)) + 1e-9
    volatility_ratio = pstdev(values) / baseline
    return max(0.0, min(1.0, 1.0 / (1.0 + max(volatility_ratio, 0.0))))


def _dependency_penalty(profits: list[float]) -> float:
    positive_profits = [max(value, 0.0) for value in profits]
    total_positive = sum(positive_profits)
    if total_positive <= 0.0 or not positive_profits:
        return 0.0

    dominant_share = max(positive_profits) / total_positive
    ideal_share = 1.0 / len(positive_profits)
    normalized_dependency = max(dominant_share - ideal_share, 0.0) / max(1.0 - ideal_share, 1e-9)
    return max(0.0, min(1.0, 1.0 - normalized_dependency))


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
    *,
    mode: str = "robust",
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
        mode=mode,
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


def score_walk_forward_results(
    windows: list[tuple[dict[str, Any], dict[str, Any], str]],
    filters: MinerFilterConfig,
    *,
    minimum_window_pass_rate: float = 1.0,
) -> ScoreBreakdown:
    if not windows:
        return ScoreBreakdown(
            score=0.0,
            mode="robust_walk_forward",
            profit_factor=0.0,
            stability=0.0,
            expectancy=0.0,
            average_return_per_trade=0.0,
            pnl_variance=0.0,
            trade_count_factor=0.0,
            drawdown_penalty=0.0,
            consistency=0.0,
            overfit_penalty=0.0,
            temporal_stability=0.0,
            passed_filters=False,
            rejection_reason="walk_forward:no_windows",
            window_scores=[],
            walk_forward_metrics=WalkForwardAggregateMetrics(
                total_windows=0,
                approved_windows=0,
                window_pass_rate=0.0,
                average_train_profit=0.0,
                average_test_profit=0.0,
                average_train_drawdown=0.0,
                average_test_drawdown=0.0,
                average_train_profit_factor=0.0,
                average_test_profit_factor=0.0,
                stability_between_windows=0.0,
                dependency_penalty=0.0,
            ),
        )

    window_scores: list[WalkForwardWindowScore] = []
    train_profits: list[float] = []
    test_profits: list[float] = []
    train_drawdowns: list[float] = []
    test_drawdowns: list[float] = []
    train_profit_factors: list[float] = []
    test_profit_factors: list[float] = []
    expectancies: list[float] = []
    average_returns: list[float] = []
    variances: list[float] = []

    for window_index, (train_result, test_result, label) in enumerate(windows):
        window_score = score_train_test_results(train_result, test_result, filters, mode="robust_walk_forward")
        train_metrics = window_score.train_metrics or summarize_backtest_metrics(train_result)
        test_metrics = window_score.test_metrics or summarize_backtest_metrics(test_result)
        window_scores.append(
            WalkForwardWindowScore(
                window_index=window_index,
                label=label,
                score=window_score.score,
                passed_filters=window_score.passed_filters,
                rejection_reason=window_score.rejection_reason,
                consistency=window_score.consistency,
                overfit_penalty=window_score.overfit_penalty,
                temporal_stability=window_score.temporal_stability,
                train_metrics=train_metrics,
                test_metrics=test_metrics,
            )
        )
        train_profits.append(train_metrics.net_profit)
        test_profits.append(test_metrics.net_profit)
        train_drawdowns.append(train_metrics.max_drawdown)
        test_drawdowns.append(test_metrics.max_drawdown)
        train_profit_factors.append(train_metrics.profit_factor if isfinite(train_metrics.profit_factor) else 1.5)
        test_profit_factors.append(test_metrics.profit_factor if isfinite(test_metrics.profit_factor) else 1.5)
        expectancies.append(test_metrics.expectancy)
        average_returns.append(test_metrics.average_return_per_trade)
        variances.append(test_metrics.pnl_variance)

    approved_windows = sum(1 for window_score in window_scores if window_score.passed_filters)
    total_windows = len(window_scores)
    window_pass_rate = approved_windows / total_windows
    profit_stability = _series_stability(test_profits)
    drawdown_stability = _series_stability(test_drawdowns)
    consistency = max(
        0.0,
        min(
            1.0,
            (_mean_or_zero([item.consistency for item in window_scores]) * 0.45)
            + (profit_stability * 0.30)
            + (drawdown_stability * 0.25),
        ),
    )
    dependency_penalty = _dependency_penalty(test_profits)
    overfit_penalty = _mean_or_zero([item.overfit_penalty for item in window_scores]) * dependency_penalty
    temporal_stability = (
        (_mean_or_zero([item.temporal_stability for item in window_scores]) * 0.50)
        + (profit_stability * 0.30)
        + (drawdown_stability * 0.20)
    )
    trade_count_factor = min(
        sum(item.test_metrics.total_trades for item in window_scores) / max(filters.min_trades * total_windows * 2, 1),
        1.0,
    )
    average_test_drawdown = _mean_or_zero(test_drawdowns)
    drawdown_penalty = 1.0 / (1.0 + log1p(max(average_test_drawdown, 0.0)))
    average_train_profit = _mean_or_zero(train_profits)
    average_test_profit = _mean_or_zero(test_profits)
    average_train_profit_factor = _mean_or_zero(train_profit_factors)
    average_test_profit_factor = _mean_or_zero(test_profit_factors)

    aggregate_metrics = WalkForwardAggregateMetrics(
        total_windows=total_windows,
        approved_windows=approved_windows,
        window_pass_rate=window_pass_rate,
        average_train_profit=average_train_profit,
        average_test_profit=average_test_profit,
        average_train_drawdown=_mean_or_zero(train_drawdowns),
        average_test_drawdown=average_test_drawdown,
        average_train_profit_factor=average_train_profit_factor,
        average_test_profit_factor=average_test_profit_factor,
        stability_between_windows=(profit_stability * 0.60) + (drawdown_stability * 0.40),
        dependency_penalty=dependency_penalty,
    )

    passed_filters = approved_windows > 0 and window_pass_rate >= minimum_window_pass_rate
    rejection_reason = None
    if not passed_filters:
        rejection_reason = "walk_forward:window_pass_rate"
        for window_score in window_scores:
            if not window_score.passed_filters and window_score.rejection_reason:
                rejection_reason = f"walk_forward:{window_score.rejection_reason}"
                break

    average_window_score = _mean_or_zero([item.score for item in window_scores]) / 100.0
    test_profit_component = log1p(max(average_test_profit, 0.0))
    train_profit_component = log1p(max(average_train_profit, 0.0))
    expectancy_component = log1p(max(_mean_or_zero(expectancies), 0.0))
    variance_penalty = _variance_penalty(_mean_or_zero(variances))
    profit_factor_component = _bounded_profit_factor(average_test_profit_factor, filters.min_profit_factor)

    raw_score = (
        (average_window_score * 0.22)
        + (test_profit_component * 0.16)
        + (train_profit_component * 0.06)
        + (drawdown_penalty * 0.10)
        + (profit_factor_component * 0.10)
        + (expectancy_component * 0.08)
        + (trade_count_factor * 0.08)
        + (temporal_stability * 0.08)
        + (consistency * 0.05)
        + (overfit_penalty * 0.04)
        + (aggregate_metrics.stability_between_windows * 0.03)
    )

    final_score = raw_score * max(window_pass_rate, 0.1) * max(dependency_penalty, 0.1) * max(consistency, 0.1)

    return ScoreBreakdown(
        score=round(final_score * 100, 4),
        mode="robust_walk_forward",
        profit_factor=average_test_profit_factor,
        stability=_mean_or_zero([item.test_metrics.stability for item in window_scores]),
        expectancy=_mean_or_zero(expectancies),
        average_return_per_trade=_mean_or_zero(average_returns),
        pnl_variance=_mean_or_zero(variances),
        trade_count_factor=trade_count_factor,
        drawdown_penalty=drawdown_penalty,
        consistency=consistency,
        overfit_penalty=overfit_penalty,
        temporal_stability=temporal_stability,
        passed_filters=passed_filters,
        rejection_reason=rejection_reason,
        train_metrics=window_scores[0].train_metrics,
        test_metrics=window_scores[-1].test_metrics,
        window_scores=window_scores,
        walk_forward_metrics=aggregate_metrics,
    )
