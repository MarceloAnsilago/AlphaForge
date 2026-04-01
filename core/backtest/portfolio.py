from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.backtest.events import (
    order_filled,
    order_intent_cancelled,
    order_intent_created,
    position_closed,
    position_opened,
    signal_rejected,
)
from core.backtest.execution_model import DeterministicExecutionModel
from core.backtest.types import BacktestArtifacts, OrderIntent, Position, Signal, Trade


@dataclass(slots=True)
class BacktestPortfolio:
    execution_model: DeterministicExecutionModel
    open_position: Position | None = None
    pending_entry_intent: OrderIntent | None = None
    pending_exit_intent: OrderIntent | None = None
    trades: list[Trade] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_entries: int = 0

    def process_pending_fills(self, candle_index: int, candle: pd.Series) -> None:
        candle_time = candle["time"]
        open_price = float(candle["open"])

        if self.pending_exit_intent is not None and self.pending_exit_intent.eligible_index <= candle_index:
            if self.open_position is None:
                self.events.append(
                    order_intent_cancelled(
                        self.pending_exit_intent,
                        candle_index,
                        candle_time,
                        "position_missing_at_fill",
                    ).to_dict()
                )
            else:
                exit_fill = self.execution_model.fill_intent(
                    self.pending_exit_intent,
                    candle_index,
                    candle_time,
                    open_price,
                    reference_label=self.execution_model.fill_policy.name,
                )
                trade = self.execution_model.build_trade(self.open_position, exit_fill, exit_reason="signal")
                self.trades.append(trade)
                self.events.append(order_filled(exit_fill).to_dict())
                self.events.append(position_closed(trade).to_dict())
                self.open_position = None
            self.pending_exit_intent = None

        if self.pending_entry_intent is not None and self.pending_entry_intent.eligible_index <= candle_index:
            if self.open_position is not None:
                self.events.append(
                    order_intent_cancelled(
                        self.pending_entry_intent,
                        candle_index,
                        candle_time,
                        "position_already_open_at_fill",
                    ).to_dict()
                )
            else:
                entry_fill = self.execution_model.fill_intent(
                    self.pending_entry_intent,
                    candle_index,
                    candle_time,
                    open_price,
                    reference_label=self.execution_model.fill_policy.name,
                )
                position = self.execution_model.build_position(entry_fill)
                self.open_position = position
                self.events.append(order_filled(entry_fill).to_dict())
                self.events.append(position_opened(position).to_dict())
            self.pending_entry_intent = None

    def capture_signals(
        self,
        candle_index: int,
        candle: pd.Series,
        entry_signals: list[Signal],
        exit_signals: list[Signal],
    ) -> None:
        candle_time = candle["time"]

        if self.open_position is not None:
            chosen_exit_signal = self.execution_model.select_exit_signal(exit_signals, self.open_position.side)
            if chosen_exit_signal is not None:
                if self.pending_exit_intent is None:
                    self.pending_exit_intent = self.execution_model.build_exit_intent(chosen_exit_signal, self.open_position)
                    self.events.append(order_intent_created(self.pending_exit_intent).to_dict())
                else:
                    self.events.append(signal_rejected(candle_index, candle_time, [chosen_exit_signal], "pending_exit_exists").to_dict())

            if entry_signals:
                self.events.append(signal_rejected(candle_index, candle_time, entry_signals, "position_already_open").to_dict())
            return

        if exit_signals:
            self.events.append(signal_rejected(candle_index, candle_time, exit_signals, "no_open_position").to_dict())

        if self.pending_entry_intent is not None:
            if entry_signals:
                self.events.append(signal_rejected(candle_index, candle_time, entry_signals, "pending_entry_exists").to_dict())
            return

        chosen_entry_signal = self.execution_model.select_entry_signal(entry_signals)
        if chosen_entry_signal is None:
            if entry_signals:
                self.ambiguous_entries += 1
                self.events.append(signal_rejected(candle_index, candle_time, entry_signals, "ambiguous_direction").to_dict())
            return

        self.pending_entry_intent = self.execution_model.build_entry_intent(chosen_entry_signal)
        self.events.append(order_intent_created(self.pending_entry_intent).to_dict())

    def finalize(self, last_index: int, last_candle: pd.Series) -> None:
        last_time = last_candle["time"]
        last_close = float(last_candle["close"])

        if self.pending_entry_intent is not None:
            self.events.append(
                order_intent_cancelled(self.pending_entry_intent, last_index, last_time, "end_of_data").to_dict()
            )
            self.pending_entry_intent = None

        if self.pending_exit_intent is not None:
            self.events.append(
                order_intent_cancelled(self.pending_exit_intent, last_index, last_time, "end_of_data").to_dict()
            )
            self.pending_exit_intent = None

        if self.open_position is None:
            return

        exit_fill = self.execution_model.fill_exit_at_reference(
            self.open_position,
            last_index,
            last_time,
            last_close,
            reference_label="end_of_data_close",
        )
        trade = self.execution_model.build_trade(self.open_position, exit_fill, exit_reason="end_of_data")
        self.trades.append(trade)
        self.events.append(order_filled(exit_fill).to_dict())
        self.events.append(position_closed(trade).to_dict())
        self.open_position = None

    def snapshot(self) -> BacktestArtifacts:
        return BacktestArtifacts(
            trades=list(self.trades),
            events=list(self.events),
            ambiguous_entries=self.ambiguous_entries,
        )
