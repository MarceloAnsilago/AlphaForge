from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.backtest.types import Fill, OrderIntent, Position, Signal, Trade


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
            "signal_types": [signal.type for signal in signals],
            "signal_sides": [signal.side for signal in signals],
            "group_ids": [signal.group_id for signal in signals],
        },
    )


def order_intent_created(intent: OrderIntent) -> BacktestEvent:
    return BacktestEvent(
        event_type="order_intent_created",
        index=intent.signal_index,
        time=intent.signal_time,
        side=intent.side,
        price=intent.signal_price,
        details={
            "action": intent.action,
            "eligible_index": intent.eligible_index,
            "group_id": intent.group_id,
            "reason": intent.reason,
        },
    )


def order_intent_cancelled(intent: OrderIntent, index: int, time: Any, reason: str) -> BacktestEvent:
    return BacktestEvent(
        event_type="order_intent_cancelled",
        index=index,
        time=time,
        side=intent.side,
        price=intent.signal_price,
        details={
            "action": intent.action,
            "signal_index": intent.signal_index,
            "eligible_index": intent.eligible_index,
            "group_id": intent.group_id,
            "reason": reason,
        },
    )


def order_filled(fill: Fill) -> BacktestEvent:
    return BacktestEvent(
        event_type="order_filled",
        index=fill.index,
        time=fill.time,
        side=fill.execution_side,
        price=fill.price,
        details={
            "action": fill.action,
            "position_side": fill.position_side,
            "reference_label": fill.reference_label,
            "reference_price": fill.reference_price,
            "spread_cost": fill.spread_cost,
            "slippage_cost": fill.slippage_cost,
            "signal_index": fill.signal_index,
            "group_id": fill.group_id,
        },
    )


def position_opened(position: Position) -> BacktestEvent:
    return BacktestEvent(
        event_type="position_opened",
        index=position.entry_index,
        time=position.entry_time,
        side=position.side,
        price=position.entry_price,
        details={
            "entry_signal_index": position.entry_signal_index,
            "entry_group_id": position.entry_group_id,
            "entry_reference_price": position.entry_reference_price,
        },
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
            "entry_signal_index": trade.entry_signal_index,
            "entry_group_id": trade.entry_group_id,
            "exit_signal_index": trade.exit_signal_index,
            "exit_group_id": trade.exit_group_id,
            "exit_reason": trade.exit_reason,
            "pnl": trade.pnl,
            "spread_cost": trade.spread_cost,
            "slippage_cost": trade.slippage_cost,
        },
    )
