from __future__ import annotations

from hashlib import sha256
from typing import Any

import json
import uuid

import pandas as pd

from core.backtest_engine import run_backtest
from domain.strategy.normalizer import normalize_strategy
from domain.strategy.spec import StrategyDraft, StrategySpec
from infra.db.supabase_client import utc_now_iso
from infra.repositories.backtest_repository import BacktestRepository
from services.strategy_service import strategy_spec_fingerprint


def _stable_json_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _iso_or_none(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def candle_frame_fingerprint(candles: pd.DataFrame) -> str:
    if candles.empty:
        return _stable_json_hash({"candles": []})

    normalized = candles.copy()
    normalized["time"] = normalized["time"].astype(str)
    records = normalized.to_dict(orient="records")
    return _stable_json_hash({"candles": records})


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
        run_payload = {
            "strategy_version_id": strategy_version["id"],
            "strategy_id": strategy_version["strategy_id"],
            "symbol": strategy_spec.market.get("symbol"),
            "timeframe": strategy_spec.market.get("timeframe"),
            "period_start": period_start,
            "period_end": period_end,
            "candle_count": int(len(candles)),
            "execution_parameters": execution_parameters,
            "candle_fingerprint": candle_fingerprint,
            "strategy_fingerprint": strategy_fingerprint,
            "input_fingerprint": _stable_json_hash(
                {
                    "strategy_version_id": strategy_version["id"],
                    "strategy_fingerprint": strategy_fingerprint,
                    "candle_fingerprint": candle_fingerprint,
                    "execution_parameters": execution_parameters,
                    "symbol": strategy_spec.market.get("symbol"),
                    "timeframe": strategy_spec.market.get("timeframe"),
                    "period_start": period_start,
                    "period_end": period_end,
                }
            ),
            "id": str(uuid.uuid4()),
            "created_at": utc_now_iso(),
        }
        run_row = self._backtest_repository.create_backtest_run(run_payload)

        summary = dict(backtest_result["summary"])
        metrics_row = self._backtest_repository.create_backtest_metrics(
            {
                "id": str(uuid.uuid4()),
                "backtest_run_id": run_row["id"],
                "summary": summary,
                "total_trades": int(summary.get("total_trades", 0)),
                "winning_trades": int(summary.get("winning_trades", 0)),
                "losing_trades": int(summary.get("losing_trades", 0)),
                "win_rate": float(summary.get("win_rate", 0.0)),
                "gross_profit": float(summary.get("gross_profit", 0.0)),
                "gross_loss": float(summary.get("gross_loss", 0.0)),
                "net_profit": float(summary.get("net_profit", 0.0)),
                "average_pnl": float(summary.get("average_pnl", 0.0)),
                "average_holding_bars": float(summary.get("average_holding_bars", 0.0)),
                "max_drawdown": float(summary.get("max_drawdown", 0.0)),
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
