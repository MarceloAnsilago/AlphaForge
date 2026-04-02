from __future__ import annotations

from typing import Any

import pandas as pd


def build_equity_curve_frame(trades: list[dict[str, Any]]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=["time", "equity"])

    frame = pd.DataFrame(trades).copy()
    if frame.empty or "pnl" not in frame.columns:
        return pd.DataFrame(columns=["time", "equity"])

    frame["pnl"] = pd.to_numeric(frame["pnl"], errors="coerce").fillna(0.0)
    if "exit_time" in frame.columns:
        frame["time"] = pd.to_datetime(frame["exit_time"], errors="coerce")
    elif "entry_time" in frame.columns:
        frame["time"] = pd.to_datetime(frame["entry_time"], errors="coerce")
    else:
        frame["time"] = pd.RangeIndex(start=0, stop=len(frame), step=1)
    frame["equity"] = frame["pnl"].cumsum()
    return frame.loc[:, ["time", "equity"]]


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
    return pd.DataFrame(rows)


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
