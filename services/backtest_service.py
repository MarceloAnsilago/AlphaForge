from __future__ import annotations

from typing import Any

import uuid
from math import isfinite

import pandas as pd

from core.backtest_engine import run_backtest
from domain.miner.fingerprint import backtest_input_fingerprint, candle_frame_fingerprint, strategy_spec_fingerprint
from domain.miner.scoring import compute_stability
from domain.strategy.normalizer import normalize_strategy
from domain.strategy.spec import StrategyDraft, StrategySpec
from infra.db.supabase_client import utc_now_iso
from infra.repositories.backtest_repository import BacktestRepository

def _iso_or_none(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, float) and not isfinite(value):
        return "inf" if value > 0 else "-inf"
    return value


def _finite_metric(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if isfinite(number):
        return number
    return 1_000_000.0 if number > 0 else default


class BacktestService:
    def __init__(self, backtest_repository: BacktestRepository) -> None:
        self._backtest_repository = backtest_repository

    def run_and_persist_backtest(
        self,
        *,
        strategy_version: dict[str, Any],
        strategy: dict[str, Any] | StrategyDraft | StrategySpec,
        candles: pd.DataFrame,
        execution_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        strategy_spec = normalize_strategy(strategy)
        result = run_backtest(strategy_spec, candles)
        persistence = self.persist_backtest_result(
            strategy_version=strategy_version,
            strategy_spec=strategy_spec,
            candles=candles,
            backtest_result=result,
            execution_parameters=execution_parameters,
        )
        return {
            "result": result,
            "persistence": persistence,
            "strategy_spec": strategy_spec,
        }

    def persist_backtest_result(
        self,
        *,
        strategy_version: dict[str, Any],
        strategy_spec: StrategySpec,
        candles: pd.DataFrame,
        backtest_result: dict[str, Any],
        execution_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        execution_parameters = dict(execution_parameters or {})
        strategy_fingerprint = strategy_version.get("strategy_fingerprint") or strategy_spec_fingerprint(strategy_spec)
        candle_fingerprint = candle_frame_fingerprint(candles)
        period_start = _iso_or_none(candles.iloc[0]["time"]) if not candles.empty else None
        period_end = _iso_or_none(candles.iloc[-1]["time"]) if not candles.empty else None
        input_fingerprint = backtest_input_fingerprint(
            strategy_version_id=strategy_version["id"],
            strategy_spec=strategy_spec,
            candles=candles,
            execution_parameters=execution_parameters,
        )
        run_payload = {
            "strategy_version_id": strategy_version["id"],
            "strategy_id": strategy_version["strategy_id"],
            "symbol": strategy_spec.market.get("symbol"),
            "timeframe": strategy_spec.market.get("timeframe"),
            "period_start": period_start,
            "period_end": period_end,
            "candle_count": int(len(candles)),
            "evaluation_mode": execution_parameters.get("evaluation_mode"),
            "dataset_role": execution_parameters.get("dataset_role"),
            "dataset_id": execution_parameters.get("dataset_id"),
            "campaign_id": execution_parameters.get("campaign_id"),
            "partition_origin": execution_parameters.get("partition_origin"),
            "window_index": execution_parameters.get("window_index"),
            "window_label": execution_parameters.get("window_label"),
            "execution_parameters": execution_parameters,
            "candle_fingerprint": candle_fingerprint,
            "strategy_fingerprint": strategy_fingerprint,
            "input_fingerprint": input_fingerprint,
            "status": "completed",
            "passed_filters": None,
            "score": None,
            "top_rank": None,
            "rejection_reason": None,
            "is_top_strategy": False,
            "id": str(uuid.uuid4()),
            "created_at": utc_now_iso(),
        }
        run_row = self._backtest_repository.create_backtest_run(run_payload)

        raw_summary = dict(backtest_result["summary"])
        summary = {key: _json_safe_value(value) for key, value in raw_summary.items()}
        metrics_row = self._backtest_repository.create_backtest_metrics(
            {
                "id": str(uuid.uuid4()),
                "backtest_run_id": run_row["id"],
                "summary": summary,
                "total_trades": int(raw_summary.get("total_trades", 0)),
                "winning_trades": int(raw_summary.get("winning_trades", 0)),
                "losing_trades": int(raw_summary.get("losing_trades", 0)),
                "win_rate": _finite_metric(raw_summary.get("win_rate", 0.0)),
                "gross_profit": _finite_metric(raw_summary.get("gross_profit", 0.0)),
                "gross_loss": _finite_metric(raw_summary.get("gross_loss", 0.0)),
                "net_profit": _finite_metric(raw_summary.get("net_profit", 0.0)),
                "average_pnl": _finite_metric(raw_summary.get("average_pnl", 0.0)),
                "average_return_per_trade": _finite_metric(raw_summary.get("average_return_per_trade", 0.0)),
                "average_holding_bars": _finite_metric(raw_summary.get("average_holding_bars", 0.0)),
                "max_drawdown": _finite_metric(raw_summary.get("max_drawdown", 0.0)),
                "profit_factor": _finite_metric(raw_summary.get("profit_factor", 0.0)),
                "expectancy": _finite_metric(raw_summary.get("expectancy", 0.0)),
                "pnl_variance": _finite_metric(raw_summary.get("pnl_variance", 0.0)),
                "stability": _finite_metric(compute_stability(backtest_result)),
                "created_at": utc_now_iso(),
            }
        )

        trades_frame = backtest_result["trades"]
        trade_rows: list[dict[str, Any]] = []
        if not trades_frame.empty:
            for trade_number, (_, trade) in enumerate(trades_frame.iterrows(), start=1):
                trade_rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "backtest_run_id": run_row["id"],
                        "trade_number": trade_number,
                        "side": trade["side"],
                        "entry_time": _iso_or_none(trade.get("entry_time")),
                        "exit_time": _iso_or_none(trade.get("exit_time")),
                        "entry_price": float(trade["entry_price"]),
                        "exit_price": float(trade["exit_price"]),
                        "pnl": float(trade["pnl"]),
                        "holding_bars": int(trade["holding_bars"]),
                        "trade_payload": {
                            key: (value.isoformat() if hasattr(value, "isoformat") else value)
                            for key, value in trade.to_dict().items()
                        },
                        "created_at": utc_now_iso(),
                    }
                )
        trade_records = self._backtest_repository.create_backtest_trades(trade_rows)

        return {
            "backtest_run": run_row,
            "backtest_metrics": metrics_row,
            "backtest_trades": trade_records,
        }
