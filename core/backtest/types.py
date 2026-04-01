from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd


SignalType = Literal["entry", "exit"]
TradeSide = Literal["BUY", "SELL"]
IntentAction = Literal["ENTRY", "EXIT"]


def normalize_signal_side(side: str | None, direction: str) -> str | None:
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


def opposite_side(side: TradeSide) -> TradeSide:
    if side == "BUY":
        return "SELL"
    return "BUY"


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
    def from_payload(cls, payload: dict[str, Any], direction: str | None = None) -> "Signal":
        side = payload.get("side")
        if direction is not None:
            side = normalize_signal_side(side, direction)
        return cls(
            type=payload["type"],
            group_id=str(payload["group_id"]),
            index=int(payload["index"]),
            time=payload["time"],
            price=float(payload["price"]),
            side=side,
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
class SignalFrame:
    frame: pd.DataFrame

    COLUMNS = [
        "index",
        "timestamp",
        "signal_type",
        "entry_signal",
        "exit_signal",
        "side",
        "price",
        "group_id",
        "metadata",
    ]

    @classmethod
    def empty(cls) -> "SignalFrame":
        return cls(pd.DataFrame(columns=cls.COLUMNS))

    @classmethod
    def from_evaluation(cls, evaluation_result: dict[str, Any], direction: str) -> "SignalFrame":
        rows: list[dict[str, Any]] = []
        for signal_type, entry_flag, exit_flag in (("entry", True, False), ("exit", False, True)):
            for payload in evaluation_result.get(f"{signal_type}_signals", []):
                rows.append(
                    {
                        "index": int(payload["index"]),
                        "timestamp": payload["time"],
                        "signal_type": signal_type,
                        "entry_signal": entry_flag,
                        "exit_signal": exit_flag,
                        "side": normalize_signal_side(payload.get("side"), direction),
                        "price": float(payload["price"]),
                        "group_id": str(payload["group_id"]),
                        "metadata": payload.get("metadata", {}),
                    }
                )

        if not rows:
            return cls.empty()

        frame = pd.DataFrame(rows, columns=cls.COLUMNS)
        frame = frame.sort_values(
            by=["index", "exit_signal", "entry_signal", "group_id"],
            ascending=[True, False, False, True],
            kind="stable",
        ).reset_index(drop=True)
        return cls(frame)

    def signals_at(self, index: int, signal_type: SignalType) -> list[Signal]:
        if self.frame.empty:
            return []

        flag_column = "entry_signal" if signal_type == "entry" else "exit_signal"
        subset = self.frame.loc[(self.frame["index"] == index) & (self.frame[flag_column])]
        signals: list[Signal] = []
        for row in subset.to_dict(orient="records"):
            signals.append(
                Signal(
                    type=signal_type,
                    group_id=str(row["group_id"]),
                    index=int(row["index"]),
                    time=row["timestamp"],
                    price=float(row["price"]),
                    side=row.get("side"),
                    metadata=row["metadata"] if isinstance(row.get("metadata"), dict) else {},
                )
            )
        return signals

    def entry_signals_at(self, index: int) -> list[Signal]:
        return self.signals_at(index, "entry")

    def exit_signals_at(self, index: int) -> list[Signal]:
        return self.signals_at(index, "exit")


@dataclass(slots=True)
class FillPolicy:
    name: str = "next_candle_open"
    fixed_spread: float = 0.0
    slippage: float = 0.0

    def execution_price(self, reference_price: float, execution_side: TradeSide) -> tuple[float, float, float]:
        half_spread = max(float(self.fixed_spread), 0.0) / 2
        slippage = max(float(self.slippage), 0.0)
        if execution_side == "BUY":
            return reference_price + half_spread + slippage, half_spread, slippage
        return reference_price - half_spread - slippage, half_spread, slippage


@dataclass(slots=True)
class OrderIntent:
    action: IntentAction
    side: TradeSide
    signal_index: int
    signal_time: Any
    signal_price: float
    group_id: str | None
    eligible_index: int
    reason: str = "signal"


@dataclass(slots=True)
class Fill:
    action: IntentAction
    position_side: TradeSide
    execution_side: TradeSide
    index: int
    time: Any
    reference_price: float
    price: float
    spread_cost: float
    slippage_cost: float
    signal_index: int | None
    signal_time: Any | None
    signal_price: float | None
    group_id: str | None
    reference_label: str


@dataclass(slots=True)
class Position:
    side: TradeSide
    entry_signal_index: int
    entry_signal_time: Any
    entry_index: int
    entry_time: Any
    entry_price: float
    entry_reference_price: float
    entry_group_id: str | None
    entry_spread_cost: float
    entry_slippage_cost: float


@dataclass(slots=True)
class Trade:
    side: TradeSide
    entry_signal_index: int
    entry_signal_time: Any
    entry_index: int
    entry_time: Any
    entry_price: float
    entry_reference_price: float
    entry_group_id: str | None
    exit_signal_index: int | None
    exit_signal_time: Any | None
    exit_index: int
    exit_time: Any
    exit_price: float
    exit_reference_price: float
    exit_group_id: str | None
    holding_bars: int
    pnl: float
    spread_cost: float
    slippage_cost: float
    exit_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "entry_signal_index": self.entry_signal_index,
            "entry_signal_time": self.entry_signal_time,
            "entry_index": self.entry_index,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "entry_reference_price": self.entry_reference_price,
            "entry_group_id": self.entry_group_id,
            "exit_signal_index": self.exit_signal_index,
            "exit_signal_time": self.exit_signal_time,
            "exit_index": self.exit_index,
            "exit_time": self.exit_time,
            "exit_price": self.exit_price,
            "exit_reference_price": self.exit_reference_price,
            "exit_group_id": self.exit_group_id,
            "holding_bars": self.holding_bars,
            "pnl": self.pnl,
            "spread_cost": self.spread_cost,
            "slippage_cost": self.slippage_cost,
            "exit_reason": self.exit_reason,
        }


@dataclass(slots=True)
class BacktestArtifacts:
    trades: list[Trade] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_entries: int = 0
