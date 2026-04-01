from __future__ import annotations

from dataclasses import dataclass
from math import log1p
from typing import Any

import pandas as pd

from domain.miner.space import MinerFilterConfig


@dataclass(slots=True)
class ScoreBreakdown:
    score: float
    profit_factor: float
    stability: float
    trade_count_factor: float
    drawdown_penalty: float
    passed_filters: bool
    rejection_reason: str | None


def compute_profit_factor(summary: dict[str, Any]) -> float:
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
    return max(0.0, min(1.0, (smoothness * 0.6) + (win_rate * 0.4)))


def passes_filters(summary: dict[str, Any], filters: MinerFilterConfig) -> tuple[bool, str | None]:
    total_trades = int(summary.get("total_trades", 0))
    net_profit = float(summary.get("net_profit", 0.0))
    max_drawdown = abs(float(summary.get("max_drawdown", 0.0)))
    profit_factor = compute_profit_factor(summary)

    if total_trades < filters.min_trades:
        return False, "min_trades"
    if net_profit <= filters.min_net_profit:
        return False, "net_profit"
    if max_drawdown > filters.max_drawdown:
        return False, "max_drawdown"
    if profit_factor < filters.min_profit_factor:
        return False, "profit_factor"
    return True, None


def score_backtest_result(backtest_result: dict[str, Any], filters: MinerFilterConfig) -> ScoreBreakdown:
    summary = backtest_result["summary"]
    passed_filters, rejection_reason = passes_filters(summary, filters)
    profit_factor = compute_profit_factor(summary)
    stability = compute_stability(backtest_result)
    total_trades = int(summary.get("total_trades", 0))
    net_profit = max(float(summary.get("net_profit", 0.0)), 0.0)
    max_drawdown = abs(float(summary.get("max_drawdown", 0.0)))

    trade_count_factor = min(total_trades / max(filters.min_trades * 2, 1), 1.0)
    drawdown_penalty = 1.0 / (1.0 + log1p(max_drawdown))
    profit_component = log1p(net_profit)
    profit_factor_component = min(profit_factor / max(filters.min_profit_factor * 2, 1e-9), 1.5)

    raw_score = (
        (profit_component * 0.35)
        + (drawdown_penalty * 0.20)
        + (stability * 0.25)
        + (trade_count_factor * 0.10)
        + (profit_factor_component * 0.10)
    )
    score = round(raw_score * 100, 4)

    return ScoreBreakdown(
        score=score,
        profit_factor=profit_factor,
        stability=stability,
        trade_count_factor=trade_count_factor,
        drawdown_penalty=drawdown_penalty,
        passed_filters=passed_filters,
        rejection_reason=rejection_reason,
    )
