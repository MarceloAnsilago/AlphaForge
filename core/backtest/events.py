from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.backtest.types import Position, Signal, Trade


@dataclass(slots=True)
class BacktestEvent:
    event_type: str
    index: int
    time: Any
    side: str | None = None
    price: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "index": self.index,
            "time": self.time,
            "side": self.side,
            "price": self.price,
            "details": self.details,
        }


def signal_rejected(index: int, time: Any, signals: list[Signal], reason: str) -> BacktestEvent:
    return BacktestEvent(
        event_type="signal_rejected",
        index=index,
        time=time,
        details={
            "reason": reason,
            "signal_sides": [signal.side for signal in signals],
            "group_ids": [signal.group_id for signal in signals],
        },
    )


def position_opened(position: Position) -> BacktestEvent:
    return BacktestEvent(
        event_type="position_opened",
        index=position.entry_index,
        time=position.entry_time,
        side=position.side,
        price=position.entry_price,
        details={"entry_group_id": position.entry_group_id},
    )


def position_closed(trade: Trade) -> BacktestEvent:
    return BacktestEvent(
        event_type="position_closed",
        index=trade.exit_index,
        time=trade.exit_time,
        side=trade.side,
        price=trade.exit_price,
        details={
            "entry_index": trade.entry_index,
            "entry_group_id": trade.entry_group_id,
            "exit_group_id": trade.exit_group_id,
            "exit_reason": trade.exit_reason,
            "pnl": trade.pnl,
        },
    )

