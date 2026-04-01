from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.backtest.events import position_closed, position_opened, signal_rejected
from core.backtest.execution_model import DeterministicExecutionModel
from core.backtest.types import BacktestArtifacts, Position, Signal, Trade


@dataclass(slots=True)
class BacktestPortfolio:
    execution_model: DeterministicExecutionModel
    open_position: Position | None = None
    trades: list[Trade] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_entries: int = 0

    def process_candle(
        self,
        candle_index: int,
        candle: pd.Series,
        entry_signals: list[Signal],
        exit_signals: list[Signal],
    ) -> None:
        close_price = float(candle["close"])
        candle_time = candle["time"]

        if self.open_position is not None and self.execution_model.has_exit_for_side(exit_signals, self.open_position.side):
            trade = self.execution_model.build_trade(
                position=self.open_position,
                exit_index=candle_index,
                exit_time=candle_time,
                exit_price=close_price,
                exit_group_id=self.execution_model.resolve_exit_group_id(exit_signals, self.open_position.side),
                exit_reason="signal",
            )
            self.trades.append(trade)
            self.events.append(position_closed(trade).to_dict())
            self.open_position = None

        if self.open_position is not None:
            return

        chosen_entry_signal = self.execution_model.select_entry_signal(entry_signals)
        if chosen_entry_signal is None:
            if entry_signals:
                self.ambiguous_entries += 1
                self.events.append(signal_rejected(candle_index, candle_time, entry_signals, "ambiguous_direction").to_dict())
            return

        position = self.execution_model.build_position(chosen_entry_signal, close_price)
        self.open_position = position
        self.events.append(position_opened(position).to_dict())

    def close_at_end_of_data(self, last_index: int, last_candle: pd.Series) -> None:
        if self.open_position is None:
            return

        trade = self.execution_model.build_trade(
            position=self.open_position,
            exit_index=last_index,
            exit_time=last_candle["time"],
            exit_price=float(last_candle["close"]),
            exit_group_id=None,
            exit_reason="end_of_data",
        )
        self.trades.append(trade)
        self.events.append(position_closed(trade).to_dict())
        self.open_position = None

    def snapshot(self) -> BacktestArtifacts:
        return BacktestArtifacts(
            trades=list(self.trades),
            events=list(self.events),
            ambiguous_entries=self.ambiguous_entries,
        )

