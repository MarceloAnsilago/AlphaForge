from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from core.backtest.execution_model import DeterministicExecutionModel
from core.backtest.metrics import attach_position_side, build_performance_curve, build_summary
from core.backtest.portfolio import BacktestPortfolio
from core.backtest.types import FillPolicy, SignalFrame
from core.strategy_engine import evaluate_strategy


SignalEvaluator = Callable[[dict[str, Any], pd.DataFrame], dict[str, Any]]


@dataclass(slots=True)
class BacktestEngine:
    signal_evaluator: SignalEvaluator = evaluate_strategy

    def _prepare_candles(self, candles: pd.DataFrame) -> pd.DataFrame:
        if candles.empty:
            return candles.copy()
        return candles.sort_values("time", kind="stable").reset_index(drop=True).copy()

    def _resolve_fill_policy(self, strategy: dict[str, Any]) -> FillPolicy:
        settings = strategy.get("settings", {})
        backtest_settings = settings.get("backtest", {})
        fixed_spread = backtest_settings.get(
            "fixed_spread",
            settings.get("fixed_spread", settings.get("spread", settings.get("backtest_spread", 0.0))),
        )
        slippage = backtest_settings.get("slippage", settings.get("slippage", 0.0))
        return FillPolicy(
            name="next_candle_open",
            fixed_spread=float(fixed_spread or 0.0),
            slippage=float(slippage or 0.0),
        )

    def run(self, strategy: dict[str, Any], candles: pd.DataFrame) -> dict[str, Any]:
        if candles.empty:
            empty_trades = pd.DataFrame()
            return {
                "summary": build_summary(empty_trades),
                "trades": empty_trades,
                "performance_curve": pd.DataFrame(columns=["time", "trade_number", "equity", "peak", "drawdown"]),
                "evaluation": pd.DataFrame(),
                "signal_frame": SignalFrame.empty().frame,
                "signals": {
                    "entry_signals": [],
                    "exit_signals": [],
                    "evaluation": pd.DataFrame(),
                },
                "ambiguous_entries": 0,
                "events": [],
            }

        prepared_candles = self._prepare_candles(candles)
        signal_result = self.signal_evaluator(strategy, prepared_candles)
        direction = strategy.get("direction", "NONE")
        volume = float(strategy.get("settings", {}).get("initial_volume", 1.0))
        fill_policy = self._resolve_fill_policy(strategy)
        signal_frame = SignalFrame.from_evaluation(signal_result, direction)
        execution_model = DeterministicExecutionModel(direction=direction, volume=volume, fill_policy=fill_policy)
        portfolio = BacktestPortfolio(execution_model=execution_model)

        for index, candle in prepared_candles.iterrows():
            candle_index = int(index)
            portfolio.process_pending_fills(candle_index, candle)
            portfolio.capture_signals(
                candle_index=candle_index,
                candle=candle,
                entry_signals=signal_frame.entry_signals_at(candle_index),
                exit_signals=signal_frame.exit_signals_at(candle_index),
            )

        portfolio.finalize(int(prepared_candles.index[-1]), prepared_candles.iloc[-1])
        artifacts = portfolio.snapshot()
        trades_frame = pd.DataFrame([trade.to_dict() for trade in artifacts.trades])
        evaluation_frame = attach_position_side(signal_result["evaluation"], trades_frame)

        return {
            "summary": build_summary(trades_frame),
            "trades": trades_frame,
            "performance_curve": build_performance_curve(trades_frame),
            "evaluation": evaluation_frame,
            "signal_frame": signal_frame.frame,
            "signals": signal_result,
            "ambiguous_entries": artifacts.ambiguous_entries,
            "events": artifacts.events,
        }
