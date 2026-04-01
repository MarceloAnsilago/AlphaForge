from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from core.backtest.execution_model import DeterministicExecutionModel
from core.backtest.metrics import attach_position_side, build_performance_curve, build_summary
from core.backtest.portfolio import BacktestPortfolio
from core.strategy_engine import evaluate_strategy


SignalEvaluator = Callable[[dict[str, Any], pd.DataFrame], dict[str, Any]]


@dataclass(slots=True)
class BacktestEngine:
    signal_evaluator: SignalEvaluator = evaluate_strategy

    def run(self, strategy: dict[str, Any], candles: pd.DataFrame) -> dict[str, Any]:
        if candles.empty:
            empty_trades = pd.DataFrame()
            return {
                "summary": build_summary(empty_trades),
                "trades": empty_trades,
                "performance_curve": pd.DataFrame(columns=["time", "trade_number", "equity", "peak", "drawdown"]),
                "evaluation": pd.DataFrame(),
                "signals": {
                    "entry_signals": [],
                    "exit_signals": [],
                    "evaluation": pd.DataFrame(),
                },
                "ambiguous_entries": 0,
                "events": [],
            }

        signal_result = self.signal_evaluator(strategy, candles)
        direction = strategy.get("direction", "NONE")
        volume = float(strategy.get("settings", {}).get("initial_volume", 1.0))

        execution_model = DeterministicExecutionModel(direction=direction, volume=volume)
        portfolio = BacktestPortfolio(execution_model=execution_model)

        entry_signals_by_index = execution_model.group_signals_by_index(signal_result["entry_signals"])
        exit_signals_by_index = execution_model.group_signals_by_index(signal_result["exit_signals"])

        for index, candle in candles.iterrows():
            candle_index = int(index)
            portfolio.process_candle(
                candle_index=candle_index,
                candle=candle,
                entry_signals=entry_signals_by_index.get(candle_index, []),
                exit_signals=exit_signals_by_index.get(candle_index, []),
            )

        portfolio.close_at_end_of_data(int(candles.index[-1]), candles.iloc[-1])
        artifacts = portfolio.snapshot()
        trades_frame = pd.DataFrame([trade.to_dict() for trade in artifacts.trades])
        evaluation_frame = attach_position_side(signal_result["evaluation"], trades_frame)

        return {
            "summary": build_summary(trades_frame),
            "trades": trades_frame,
            "performance_curve": build_performance_curve(trades_frame),
            "evaluation": evaluation_frame,
            "signals": signal_result,
            "ambiguous_entries": artifacts.ambiguous_entries,
            "events": artifacts.events,
        }
