from __future__ import annotations

from typing import Any

import pandas as pd


def build_summary(trades: pd.DataFrame) -> dict[str, Any]:
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
            "max_drawdown": 0.0,
        }

    winning_trades = int((trades["pnl"] > 0).sum())
    losing_trades = int((trades["pnl"] < 0).sum())
    gross_profit = float(trades.loc[trades["pnl"] > 0, "pnl"].sum())
    gross_loss = float(trades.loc[trades["pnl"] < 0, "pnl"].sum())
    equity_curve = trades["pnl"].cumsum()
    drawdown_curve = equity_curve - equity_curve.cummax()

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
        "max_drawdown": float(drawdown_curve.min()),
    }


def build_performance_curve(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["time", "trade_number", "equity", "peak", "drawdown"])

    performance_curve = trades.loc[:, ["exit_time", "pnl"]].copy()
    performance_curve = performance_curve.rename(columns={"exit_time": "time"})
    performance_curve["trade_number"] = range(1, len(performance_curve) + 1)
    performance_curve["equity"] = performance_curve["pnl"].cumsum()
    performance_curve["peak"] = performance_curve["equity"].cummax()
    performance_curve["drawdown"] = performance_curve["equity"] - performance_curve["peak"]

    start_row = pd.DataFrame(
        [
            {
                "time": trades.iloc[0]["entry_time"],
                "trade_number": 0,
                "equity": 0.0,
                "peak": 0.0,
                "drawdown": 0.0,
            }
        ]
    )

    return pd.concat(
        [start_row, performance_curve.loc[:, ["time", "trade_number", "equity", "peak", "drawdown"]]],
        ignore_index=True,
    )


def attach_position_side(evaluation_frame: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    result = evaluation_frame.copy()
    result["position_side"] = pd.NA

    if trades.empty:
        return result

    for _, trade in trades.iterrows():
        result.loc[trade["entry_index"] : trade["exit_index"], "position_side"] = trade["side"]
    return result

