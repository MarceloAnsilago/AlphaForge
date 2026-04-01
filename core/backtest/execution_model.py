from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.backtest.types import Position, Signal, Trade


def normalize_side(side: str | None, direction: str) -> str | None:
    normalized_side = (side or direction or "").upper()
    if normalized_side in {"BUY", "SELL"}:
        return normalized_side
    if normalized_side == "BOTH":
        if direction == "BUY":
            return "BUY"
        if direction == "SELL":
            return "SELL"
        return None
    return None


@dataclass(slots=True)
class DeterministicExecutionModel:
    direction: str
    volume: float

    def normalize_signal(self, signal: dict[str, Any] | Signal) -> Signal:
        if isinstance(signal, Signal):
            payload = signal.to_dict()
        else:
            payload = signal
        normalized_signal = Signal.from_payload(payload)
        normalized_signal.side = normalize_side(normalized_signal.side, self.direction)
        return normalized_signal

    def group_signals_by_index(self, signals: list[dict[str, Any]] | list[Signal]) -> dict[int, list[Signal]]:
        grouped: dict[int, list[Signal]] = {}
        for signal in signals:
            normalized_signal = self.normalize_signal(signal)
            grouped.setdefault(normalized_signal.index, []).append(normalized_signal)
        return grouped

    def select_entry_signal(self, signals: list[Signal]) -> Signal | None:
        directional_signals = [signal for signal in signals if signal.side in {"BUY", "SELL"}]
        if not directional_signals:
            return None

        distinct_sides = {signal.side for signal in directional_signals}
        if len(distinct_sides) > 1:
            return None

        return directional_signals[0]

    def has_exit_for_side(self, signals: list[Signal], side: str) -> bool:
        for signal in signals:
            if signal.side is None or signal.side == side:
                return True
        return False

    def build_position(self, entry_signal: Signal, price: float) -> Position:
        return Position(
            side=entry_signal.side,  # type: ignore[arg-type]
            entry_index=entry_signal.index,
            entry_time=entry_signal.time,
            entry_price=price,
            entry_group_id=entry_signal.group_id,
        )

    def build_trade(
        self,
        position: Position,
        exit_index: int,
        exit_time: Any,
        exit_price: float,
        exit_group_id: str | None,
        exit_reason: str,
    ) -> Trade:
        return Trade(
            side=position.side,
            entry_index=position.entry_index,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            entry_group_id=position.entry_group_id,
            exit_index=exit_index,
            exit_time=exit_time,
            exit_price=exit_price,
            exit_group_id=exit_group_id,
            holding_bars=exit_index - position.entry_index,
            pnl=self.trade_pnl(position.entry_price, exit_price, position.side),
            exit_reason=exit_reason,
        )

    def resolve_exit_group_id(self, signals: list[Signal], side: str) -> str | None:
        for signal in signals:
            if signal.side is None or signal.side == side:
                return signal.group_id
        return None

    def trade_pnl(self, entry_price: float, exit_price: float, side: str) -> float:
        if side == "SELL":
            return (entry_price - exit_price) * self.volume
        return (exit_price - entry_price) * self.volume

