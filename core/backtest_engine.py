from __future__ import annotations

from typing import Any

import pandas as pd

from core.strategy_engine import evaluate_strategy


def _normalize_side(side: str | None, direction: str) -> str | None:
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


def _group_signals_by_index(signals: list[dict[str, Any]], direction: str) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for signal in signals:
        normalized_signal = {
            **signal,
            "side": _normalize_side(signal.get("side"), direction),
        }
        grouped.setdefault(int(signal["index"]), []).append(normalized_signal)
    return grouped


def _select_entry_signal(signals: list[dict[str, Any]]) -> dict[str, Any] | None:
    directional_signals = [signal for signal in signals if signal.get("side") in {"BUY", "SELL"}]
    if not directional_signals:
        return None

    distinct_sides = {signal["side"] for signal in directional_signals}
    if len(distinct_sides) > 1:
        return None

    return directional_signals[0]


def _has_exit_for_side(signals: list[dict[str, Any]], side: str) -> bool:
    for signal in signals:
        signal_side = signal.get("side")
        if signal_side is None or signal_side == side:
            return True
    return False


def _trade_pnl(entry_price: float, exit_price: float, side: str, volume: float) -> float:
    if side == "SELL":
        return (entry_price - exit_price) * volume
    return (exit_price - entry_price) * volume


def _build_summary(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "net_profit": 0.0,
            "average_pnl": 0.0,
            "average_holding_bars": 0.0,
        }

    winning_trades = int((trades["pnl"] > 0).sum())
    losing_trades = int((trades["pnl"] < 0).sum())
    gross_profit = float(trades.loc[trades["pnl"] > 0, "pnl"].sum())
    gross_loss = float(trades.loc[trades["pnl"] < 0, "pnl"].sum())

    return {
        "total_trades": int(len(trades)),
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": float((winning_trades / len(trades)) * 100),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit": float(trades["pnl"].sum()),
        "average_pnl": float(trades["pnl"].mean()),
        "average_holding_bars": float(trades["holding_bars"].mean()),
    }


def _build_performance_curve(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["time", "equity"])

    performance_curve = trades.loc[:, ["exit_time", "pnl"]].copy()
    performance_curve = performance_curve.rename(columns={"exit_time": "time"})
    performance_curve["equity"] = performance_curve["pnl"].cumsum()

    start_row = pd.DataFrame(
        [
            {
                "time": trades.iloc[0]["entry_time"],
                "equity": 0.0,
            }
        ]
    )

    return pd.concat(
        [start_row, performance_curve.loc[:, ["time", "equity"]]],
        ignore_index=True,
    )


def run_backtest(strategy: dict[str, Any], candles: pd.DataFrame) -> dict[str, Any]:
    if candles.empty:
        empty_trades = pd.DataFrame()
        return {
            "summary": _build_summary(empty_trades),
            "trades": empty_trades,
            "performance_curve": pd.DataFrame(columns=["time", "equity"]),
            "evaluation": pd.DataFrame(),
            "signals": {"entry": [], "exit": []},
            "ambiguous_entries": 0,
        }

    evaluation = evaluate_strategy(strategy, candles)
    direction = strategy.get("direction", "NONE")
    volume = float(strategy.get("settings", {}).get("initial_volume", 1.0))

    entry_signals_by_index = _group_signals_by_index(evaluation["entry_signals"], direction)
    exit_signals_by_index = _group_signals_by_index(evaluation["exit_signals"], direction)

    trades: list[dict[str, Any]] = []
    open_position: dict[str, Any] | None = None
    ambiguous_entries = 0

    for index, candle in candles.iterrows():
        candle_index = int(index)
        close_price = float(candle["close"])
        candle_time = candle["time"]

        current_exit_signals = exit_signals_by_index.get(candle_index, [])
        if open_position is not None and _has_exit_for_side(current_exit_signals, open_position["side"]):
            exit_group = next(
                (
                    signal["group_id"]
                    for signal in current_exit_signals
                    if signal.get("side") in {None, open_position["side"]}
                ),
                None,
            )
            trades.append(
                {
                    "side": open_position["side"],
                    "entry_index": open_position["entry_index"],
                    "entry_time": open_position["entry_time"],
                    "entry_price": open_position["entry_price"],
                    "entry_group_id": open_position["entry_group_id"],
                    "exit_index": candle_index,
                    "exit_time": candle_time,
                    "exit_price": close_price,
                    "exit_group_id": exit_group,
                    "holding_bars": candle_index - open_position["entry_index"],
                    "pnl": _trade_pnl(open_position["entry_price"], close_price, open_position["side"], volume),
                    "exit_reason": "signal",
                }
            )
            open_position = None

        if open_position is not None:
            continue

        current_entry_signals = entry_signals_by_index.get(candle_index, [])
        chosen_entry_signal = _select_entry_signal(current_entry_signals)
        if chosen_entry_signal is None:
            if current_entry_signals:
                ambiguous_entries += 1
            continue

        open_position = {
            "side": chosen_entry_signal["side"],
            "entry_index": candle_index,
            "entry_time": candle_time,
            "entry_price": close_price,
            "entry_group_id": chosen_entry_signal["group_id"],
        }

    if open_position is not None:
        last_candle = candles.iloc[-1]
        last_index = int(candles.index[-1])
        last_close = float(last_candle["close"])
        trades.append(
            {
                "side": open_position["side"],
                "entry_index": open_position["entry_index"],
                "entry_time": open_position["entry_time"],
                "entry_price": open_position["entry_price"],
                "entry_group_id": open_position["entry_group_id"],
                "exit_index": last_index,
                "exit_time": last_candle["time"],
                "exit_price": last_close,
                "exit_group_id": None,
                "holding_bars": last_index - open_position["entry_index"],
                "pnl": _trade_pnl(open_position["entry_price"], last_close, open_position["side"], volume),
                "exit_reason": "end_of_data",
            }
        )

    trades_frame = pd.DataFrame(trades)
    evaluation_frame = evaluation["evaluation"].copy()
    evaluation_frame["position_side"] = pd.NA

    if not trades_frame.empty:
        for _, trade in trades_frame.iterrows():
            evaluation_frame.loc[trade["entry_index"] : trade["exit_index"], "position_side"] = trade["side"]

    return {
        "summary": _build_summary(trades_frame),
        "trades": trades_frame,
        "performance_curve": _build_performance_curve(trades_frame),
        "evaluation": evaluation_frame,
        "signals": {
            "entry": evaluation["entry_signals"],
            "exit": evaluation["exit_signals"],
        },
        "ambiguous_entries": ambiguous_entries,
    }
