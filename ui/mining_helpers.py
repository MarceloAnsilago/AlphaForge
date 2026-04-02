from __future__ import annotations

from math import ceil
from typing import Any

import pandas as pd


def build_equity_curve_frame(trades: list[dict[str, Any]]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=["time", "equity", "drawdown", "pnl"])

    frame = pd.DataFrame(trades).copy()
    if frame.empty or "pnl" not in frame.columns:
        return pd.DataFrame(columns=["time", "equity", "drawdown", "pnl"])

    frame["pnl"] = pd.to_numeric(frame["pnl"], errors="coerce").fillna(0.0)
    if "exit_time" in frame.columns:
        frame["time"] = pd.to_datetime(frame["exit_time"], errors="coerce")
    elif "entry_time" in frame.columns:
        frame["time"] = pd.to_datetime(frame["entry_time"], errors="coerce")
    else:
        frame["time"] = pd.RangeIndex(start=0, stop=len(frame), step=1)
    frame["equity"] = frame["pnl"].cumsum()
    frame["running_max"] = frame["equity"].cummax()
    frame["drawdown"] = frame["equity"] - frame["running_max"]
    frame["trade_number"] = range(1, len(frame) + 1)
    return frame.loc[:, ["time", "trade_number", "pnl", "equity", "drawdown"]]


def filter_campaign_rows(
    rows: list[dict[str, Any]],
    summaries: dict[str, dict[str, Any] | None],
    *,
    query: str = "",
    symbol: str = "Todos",
    timeframe: str = "Todos",
) -> list[dict[str, Any]]:
    normalized_query = query.strip().lower()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        campaign_name = str(row.get("name") or row.get("id") or "").lower()
        campaign_symbol = str(row.get("symbol") or "")
        campaign_timeframe = str(row.get("timeframe") or "")
        summary = summaries.get(str(row.get("id"))) or {}

        if normalized_query and normalized_query not in campaign_name:
            continue
        if symbol != "Todos" and campaign_symbol != symbol:
            continue
        if timeframe != "Todos" and campaign_timeframe != timeframe:
            continue

        filtered.append({**row, "summary": summary})
    return filtered


def filter_strategy_rows(
    rows: list[dict[str, Any]],
    *,
    query: str = "",
    direction: str = "Todos",
    status: str = "Todos",
    minimum_score: float | None = None,
) -> list[dict[str, Any]]:
    normalized_query = query.strip().lower()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        strategy_name = str(row.get("strategy_name") or "").lower()
        strategy_direction = str(row.get("strategy_direction") or "")
        row_status = str(row.get("status") or "")
        score = row.get("score")

        if normalized_query and normalized_query not in strategy_name:
            continue
        if direction != "Todos" and strategy_direction != direction:
            continue
        if status != "Todos" and row_status != status:
            continue
        if minimum_score is not None and (score is None or float(score) < minimum_score):
            continue
        filtered.append(row)

    return filtered


def paginate_rows(
    rows: list[dict[str, Any]],
    *,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    safe_page_size = max(int(page_size), 1)
    total_items = len(rows)
    total_pages = max(ceil(total_items / safe_page_size), 1)
    current_page = min(max(int(page), 1), total_pages)
    start = (current_page - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "items": rows[start:end],
        "page": current_page,
        "page_size": safe_page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "start_index": start,
        "end_index": min(end, total_items),
    }


def summarize_strategy_rules(spec: dict[str, Any]) -> dict[str, list[str]]:
    entry_rules = spec.get("entry_rules") or []
    exit_rules = spec.get("exit_rules") or []
    return {
        "entry_rules": [_summarize_rule(rule) for rule in entry_rules],
        "exit_rules": [_summarize_rule(rule) for rule in exit_rules],
    }


def build_walk_forward_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
                "window_label",
                "dataset_role",
                "average_score",
                "pass_rate",
                "average_stability",
            ]
        )
    frame = pd.DataFrame(rows)
    if "window_index" in frame.columns:
        frame = frame.sort_values(["window_index", "dataset_role"], ascending=[True, True]).reset_index(drop=True)
    return frame


def _summarize_rule(rule: dict[str, Any]) -> str:
    source_a = _format_source(rule.get("source_a"))
    operator = str(rule.get("operator") or "N/A")
    source_b = _format_source(rule.get("source_b"))
    metadata = rule.get("metadata") or {}
    side = metadata.get("side")
    if side:
        return f"{source_a} {operator} {source_b} [{side}]"
    return f"{source_a} {operator} {source_b}"


def _format_source(source: dict[str, Any] | None) -> str:
    if not source:
        return "N/A"
    source_type = str(source.get("source_type") or "")
    value = source.get("value")
    if source_type == "fixed":
        return f"fixed:{value}"
    if source_type == "price":
        return f"price:{value}"
    return f"{source_type}:{value}"
