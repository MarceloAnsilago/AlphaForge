from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd


_COMPACT_SIGNAL_LABELS = {
    "RSI (Relative Strength Index)": "RSI",
    "MFI (Money Flow Index)": "MFI",
    "CCI (Commodity Channel Index)": "CCI",
    "ATR (Average True Range)": "ATR",
    "ADX (Average Directional Index)": "ADX",
    "RVI (Relative Vigor Index)": "RVI",
    "OBV (On Balance Volume)": "OBV",
    "A/D": "A/D",
    "Bandas de Bollinger": "Bollinger",
    "Media Movel": "Media Movel",
    "Nuvem de Ichimoku": "Ichimoku",
    "Williams %R (WPR)": "WPR",
}


def compact_signal_label(value: str | None) -> str:
    if not value:
        return "N/A"
    if value in _COMPACT_SIGNAL_LABELS:
        return _COMPACT_SIGNAL_LABELS[value]
    if " (" in value:
        return value.split(" (", maxsplit=1)[0]
    return str(value)


def build_market_signature(
    market_data: pd.DataFrame,
    market_query: dict[str, Any] | None,
) -> dict[str, Any]:
    if market_data.empty:
        return {
            "symbol": None,
            "timeframe": None,
            "rows": 0,
            "first_time": None,
            "last_time": None,
        }

    first_time = market_data.iloc[0].get("time")
    last_time = market_data.iloc[-1].get("time")
    return {
        "symbol": (market_query or {}).get("symbol"),
        "timeframe": (market_query or {}).get("timeframe"),
        "rows": int(len(market_data)),
        "first_time": str(first_time),
        "last_time": str(last_time),
    }


def summarize_builder_configuration(
    strategy_name: str,
    ready_signals: dict[str, Any],
) -> str:
    crossovers = ready_signals.get("crossovers") or {}
    if (
        crossovers.get("enabled")
        and crossovers.get("fast_source") not in {None, "", "Nao usar"}
        and crossovers.get("slow_source") not in {None, "", "Nao usar"}
    ):
        return (
            "Cruzamento "
            f"{compact_signal_label(str(crossovers.get('fast_source')))} x "
            f"{compact_signal_label(str(crossovers.get('slow_source')))}"
        )

    overbought_oversold = ready_signals.get("overbought_oversold") or {}
    if overbought_oversold.get("enabled") and overbought_oversold.get("signal") not in {None, "", "Nao usar"}:
        return (
            f"{compact_signal_label(str(overbought_oversold.get('indicator')))} "
            f"{str(overbought_oversold.get('signal'))}"
        )

    band_channels = ready_signals.get("band_channels") or {}
    if band_channels.get("enabled") and band_channels.get("signal") not in {None, "", "Nao usar"}:
        return (
            f"{compact_signal_label(str(band_channels.get('indicator')))} "
            f"{str(band_channels.get('signal'))}"
        )

    signal_settings = ready_signals.get("signal_settings") or {}
    indicators = [
        compact_signal_label(str(signal_settings.get(f"indicator_{index}")))
        for index in range(1, 5)
        if signal_settings.get(f"indicator_{index}") not in {None, "", "Nao usar", "Externo"}
    ]
    if indicators:
        highlighted = ", ".join(indicators[:2])
        return f"Indicadores {highlighted}"

    for rule in signal_settings.get("rules") or []:
        source_a = (rule.get("source_a") or {}).get("label")
        source_b = (rule.get("source_b") or {}).get("label")
        operator_label = (rule.get("operator") or {}).get("label")
        if source_a and source_b and operator_label:
            return f"{source_a} {operator_label} {source_b}"

    return strategy_name.strip() or "Builder manual"


def build_builder_attempt_record(
    *,
    attempt_number: int,
    strategy_name: str,
    ready_signals: dict[str, Any],
    payload: dict[str, Any],
    backtest_result: dict[str, Any],
    market_signature: dict[str, Any],
    created_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = created_at or datetime.now()
    summary = backtest_result["summary"]
    label = summarize_builder_configuration(strategy_name, ready_signals)
    attempt_id = f"builder-attempt-{attempt_number:03d}"
    return {
        "id": attempt_id,
        "attempt_number": int(attempt_number),
        "label": label,
        "selection_label": (
            f"Tentativa {attempt_number:02d} | {label} | "
            f"Net {float(summary['net_profit']):.2f} | PF {float(summary['profit_factor']):.2f}"
        ),
        "created_at": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": dict(summary),
        "ambiguous_entries": int(backtest_result.get("ambiguous_entries", 0)),
        "payload": payload,
        "performance_curve": backtest_result["performance_curve"].copy(),
        "trades": backtest_result["trades"].copy(),
        "market_signature": dict(market_signature),
    }


def build_builder_attempts_frame(attempts: list[dict[str, Any]]) -> pd.DataFrame:
    if not attempts:
        return pd.DataFrame(
            columns=["Tentativa", "Horario", "Configuracao", "Trades", "Net", "PF", "Drawdown", "Win rate", "Ambiguas"]
        )

    rows = []
    for attempt in reversed(attempts):
        summary = attempt.get("summary") or {}
        rows.append(
            {
                "Tentativa": int(attempt.get("attempt_number", 0)),
                "Horario": str(attempt.get("created_at") or ""),
                "Configuracao": str(attempt.get("label") or ""),
                "Trades": int(summary.get("total_trades", 0)),
                "Net": float(summary.get("net_profit", 0.0)),
                "PF": float(summary.get("profit_factor", 0.0)),
                "Drawdown": float(summary.get("max_drawdown", 0.0)),
                "Win rate": float(summary.get("win_rate", 0.0)),
                "Ambiguas": int(attempt.get("ambiguous_entries", 0)),
            }
        )
    return pd.DataFrame(rows)


def resolve_previous_attempt(
    attempts: list[dict[str, Any]],
    selected_attempt_id: str | None,
) -> dict[str, Any] | None:
    if not attempts or not selected_attempt_id:
        return None

    selected_index = None
    for index, attempt in enumerate(attempts):
        if attempt.get("id") == selected_attempt_id:
            selected_index = index
            break

    if selected_index is None or selected_index == 0:
        return None
    return attempts[selected_index - 1]
