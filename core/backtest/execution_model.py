from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.backtest.types import Fill, FillPolicy, OrderIntent, Position, Signal, Trade, opposite_side


@dataclass(slots=True)
class DeterministicExecutionModel:
    direction: str
    volume: float
    fill_policy: FillPolicy

    def select_entry_signal(self, signals: list[Signal]) -> Signal | None:
        directional_signals = [signal for signal in signals if signal.side in {"BUY", "SELL"}]
        if not directional_signals:
            return None

        distinct_sides = {signal.side for signal in directional_signals}
        if len(distinct_sides) > 1:
            return None

        return directional_signals[0]

    def select_exit_signal(self, signals: list[Signal], side: str) -> Signal | None:
        for signal in signals:
            if signal.side is None or signal.side == side:
                return signal
        return None

    def build_entry_intent(self, signal: Signal) -> OrderIntent:
        return OrderIntent(
            action="ENTRY",
            side=signal.side,  # type: ignore[arg-type]
            signal_index=signal.index,
            signal_time=signal.time,
            signal_price=signal.price,
            group_id=signal.group_id,
            eligible_index=signal.index + 1,
        )

    def build_exit_intent(self, signal: Signal, position: Position) -> OrderIntent:
        return OrderIntent(
            action="EXIT",
            side=position.side,
            signal_index=signal.index,
            signal_time=signal.time,
            signal_price=signal.price,
            group_id=signal.group_id,
            eligible_index=signal.index + 1,
        )

    def fill_intent(
        self,
        intent: OrderIntent,
        candle_index: int,
        candle_time: Any,
        reference_price: float,
        reference_label: str,
    ) -> Fill:
        execution_side = intent.side if intent.action == "ENTRY" else opposite_side(intent.side)
        fill_price, spread_cost, slippage_cost = self.fill_policy.execution_price(reference_price, execution_side)
        return Fill(
            action=intent.action,
            position_side=intent.side,
            execution_side=execution_side,
            index=candle_index,
            time=candle_time,
            reference_price=reference_price,
            price=fill_price,
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            signal_index=intent.signal_index,
            signal_time=intent.signal_time,
            signal_price=intent.signal_price,
            group_id=intent.group_id,
            reference_label=reference_label,
        )

    def fill_exit_at_reference(
        self,
        position: Position,
        candle_index: int,
        candle_time: Any,
        reference_price: float,
        reference_label: str,
    ) -> Fill:
        execution_side = opposite_side(position.side)
        fill_price, spread_cost, slippage_cost = self.fill_policy.execution_price(reference_price, execution_side)
        return Fill(
            action="EXIT",
            position_side=position.side,
            execution_side=execution_side,
            index=candle_index,
            time=candle_time,
            reference_price=reference_price,
            price=fill_price,
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            signal_index=None,
            signal_time=None,
            signal_price=None,
            group_id=None,
            reference_label=reference_label,
        )

    def build_position(self, entry_fill: Fill) -> Position:
        return Position(
            side=entry_fill.position_side,
            entry_signal_index=entry_fill.signal_index or entry_fill.index,
            entry_signal_time=entry_fill.signal_time or entry_fill.time,
            entry_index=entry_fill.index,
            entry_time=entry_fill.time,
            entry_price=entry_fill.price,
            entry_reference_price=entry_fill.reference_price,
            entry_group_id=entry_fill.group_id,
            entry_spread_cost=entry_fill.spread_cost,
            entry_slippage_cost=entry_fill.slippage_cost,
        )

    def build_trade(self, position: Position, exit_fill: Fill, exit_reason: str) -> Trade:
        return Trade(
            side=position.side,
            entry_signal_index=position.entry_signal_index,
            entry_signal_time=position.entry_signal_time,
            entry_index=position.entry_index,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            entry_reference_price=position.entry_reference_price,
            entry_group_id=position.entry_group_id,
            exit_signal_index=exit_fill.signal_index,
            exit_signal_time=exit_fill.signal_time,
            exit_index=exit_fill.index,
            exit_time=exit_fill.time,
            exit_price=exit_fill.price,
            exit_reference_price=exit_fill.reference_price,
            exit_group_id=exit_fill.group_id,
            holding_bars=exit_fill.index - position.entry_index,
            pnl=self.trade_pnl(position.entry_price, exit_fill.price, position.side),
            spread_cost=position.entry_spread_cost + exit_fill.spread_cost,
            slippage_cost=position.entry_slippage_cost + exit_fill.slippage_cost,
            exit_reason=exit_reason,
        )

    def trade_pnl(self, entry_price: float, exit_price: float, side: str) -> float:
        if side == "SELL":
            return (entry_price - exit_price) * self.volume
        return (exit_price - entry_price) * self.volume
