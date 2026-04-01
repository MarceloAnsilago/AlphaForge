from __future__ import annotations

from typing import Any

import pandas as pd


def _profit_factor_from_trades(trades: pd.DataFrame) -> float:
    gross_profit = float(trades.loc[trades["pnl"] > 0, "pnl"].sum())
    gross_loss = abs(float(trades.loc[trades["pnl"] < 0, "pnl"].sum()))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


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
            "average_return_per_trade": 0.0,
            "average_holding_bars": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "pnl_variance": 0.0,
        }

    winning_trades = int((trades["pnl"] > 0).sum())
    losing_trades = int((trades["pnl"] < 0).sum())
    gross_profit = float(trades.loc[trades["pnl"] > 0, "pnl"].sum())
    gross_loss = float(trades.loc[trades["pnl"] < 0, "pnl"].sum())
    equity_curve = trades["pnl"].cumsum()
    drawdown_curve = equity_curve - equity_curve.cummax()
    average_win = float(trades.loc[trades["pnl"] > 0, "pnl"].mean()) if winning_trades else 0.0
    average_loss = abs(float(trades.loc[trades["pnl"] < 0, "pnl"].mean())) if losing_trades else 0.0
    win_rate_ratio = float(winning_trades / len(trades))
    loss_rate_ratio = float(losing_trades / len(trades))
    expectancy = (average_win * win_rate_ratio) - (average_loss * loss_rate_ratio)
    average_return_per_trade = float(trades["pnl"].mean())
    pnl_variance = float(trades["pnl"].var(ddof=0)) if len(trades) > 1 else 0.0

    return {
        "total_trades": int(len(trades)),
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": float(win_rate_ratio * 100),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit": float(trades["pnl"].sum()),
        "average_pnl": average_return_per_trade,
        "average_return_per_trade": average_return_per_trade,
        "average_holding_bars": float(trades["holding_bars"].mean()),
        "max_drawdown": float(drawdown_curve.min()),
        "profit_factor": _profit_factor_from_trades(trades),
        "expectancy": float(expectancy),
        "pnl_variance": pnl_variance,
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
