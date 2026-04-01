from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd


SignalType = Literal["entry", "exit"]
TradeSide = Literal["BUY", "SELL"]


@dataclass(slots=True)
class Signal:
    type: SignalType
    group_id: str
    index: int
    time: Any
    price: float
    side: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Signal":
        return cls(
            type=payload["type"],
            group_id=str(payload["group_id"]),
            index=int(payload["index"]),
            time=payload["time"],
            price=float(payload["price"]),
            side=payload.get("side"),
            metadata=payload.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "group_id": self.group_id,
            "index": self.index,
            "time": self.time,
            "price": self.price,
            "side": self.side,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class Position:
    side: TradeSide
    entry_index: int
    entry_time: Any
    entry_price: float
    entry_group_id: str | None


@dataclass(slots=True)
class Trade:
    side: TradeSide
    entry_index: int
    entry_time: Any
    entry_price: float
    entry_group_id: str | None
    exit_index: int
    exit_time: Any
    exit_price: float
    exit_group_id: str | None
    holding_bars: int
    pnl: float
    exit_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "entry_index": self.entry_index,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "entry_group_id": self.entry_group_id,
            "exit_index": self.exit_index,
            "exit_time": self.exit_time,
            "exit_price": self.exit_price,
            "exit_group_id": self.exit_group_id,
            "holding_bars": self.holding_bars,
            "pnl": self.pnl,
            "exit_reason": self.exit_reason,
        }


@dataclass(slots=True)
class BacktestSignalSet:
    entry_signals: list[Signal]
    exit_signals: list[Signal]
    evaluation: pd.DataFrame


@dataclass(slots=True)
class BacktestArtifacts:
    trades: list[Trade] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_entries: int = 0

