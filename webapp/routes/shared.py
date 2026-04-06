from __future__ import annotations

import json
from typing import Any

import pandas as pd


def frame_to_records(frame: Any) -> list[dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    safe_frame = frame.copy()
    for column in safe_frame.columns:
        if pd.api.types.is_datetime64_any_dtype(safe_frame[column]):
            safe_frame[column] = safe_frame[column].astype(str)
    return safe_frame.to_dict(orient="records")


def frame_columns(frame: Any) -> list[str]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    return [str(column) for column in frame.columns]


def json_pretty(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, indent=2, ensure_ascii=True, default=str)


def build_performance_chart(frame: Any) -> dict[str, Any] | None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    chart_frame = frame.copy()
    chart_frame["time"] = chart_frame["time"].astype(str)
    return {
        "labels": chart_frame["time"].tolist(),
        "equity": [float(value) for value in chart_frame["equity"].tolist()],
        "drawdown": [float(value) for value in chart_frame["drawdown"].tolist()],
    }


def build_walk_forward_chart(frame: Any) -> dict[str, Any] | None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    chart_frame = frame.copy()
    chart_frame["window_label"] = chart_frame["window_label"].fillna("window_0").astype(str)
    return {
        "labels": chart_frame["window_label"].tolist(),
        "scores": [float(value) for value in chart_frame["average_score"].fillna(0.0).tolist()],
        "stability": [float(value) for value in chart_frame["average_stability"].fillna(0.0).tolist()],
        "pass_rate": [float(value) * 100.0 for value in chart_frame["pass_rate"].fillna(0.0).tolist()],
    }


def build_equity_chart(frame: Any) -> dict[str, Any] | None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    chart_frame = frame.copy()
    chart_frame["time"] = chart_frame["time"].astype(str)
    return {
        "labels": chart_frame["time"].tolist(),
        "equity": [float(value) for value in chart_frame["equity"].tolist()],
        "drawdown": [float(value) for value in chart_frame["drawdown"].tolist()],
        "pnl": [float(value) for value in chart_frame["pnl"].tolist()],
    }
