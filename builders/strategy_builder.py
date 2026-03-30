from __future__ import annotations

from datetime import date
from typing import Any

from core.strategy_schema import build_strategy_structure


PERIOD_LABELS = {
    "LAST_MONTH": "Ultimo mes",
    "LAST_YEAR": "Ultimo ano",
    "FULL_HISTORY": "Historico completo",
    "CUSTOM": "Periodo personalizado",
}


def derive_direction(operate_buy: str, operate_sell: str) -> str:
    buy_enabled = operate_buy == "Sim"
    sell_enabled = operate_sell == "Sim"

    if buy_enabled and sell_enabled:
        return "BOTH"
    if buy_enabled:
        return "BUY"
    if sell_enabled:
        return "SELL"
    return "NONE"


def format_timeframe_label(value: str) -> str:
    return "Corrente" if value == "CURRENT" else value


def resolve_market_timeframe(selected_timeframe: str, primary_timeframe: str) -> str | None:
    if selected_timeframe != "CURRENT":
        return selected_timeframe
    if primary_timeframe == "CURRENT":
        return None
    return primary_timeframe


def build_strategy_payload(
    strategy_name: str,
    direction: str,
    settings: dict[str, Any],
    symbol: str | None,
    timeframe: str,
    period_mode: str,
    custom_start_date: date | None,
    custom_end_date: date | None,
    risk_management: dict[str, Any],
) -> dict[str, Any]:
    market_context: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "quote_period": period_mode,
    }
    if period_mode == "CUSTOM":
        market_context["start_date"] = (
            custom_start_date.isoformat() if custom_start_date is not None else None
        )
        market_context["end_date"] = (
            custom_end_date.isoformat() if custom_end_date is not None else None
        )

    return build_strategy_structure(
        name=strategy_name,
        direction=direction,
        settings=settings,
        market=market_context,
        entry_rules=[],
        exit_rules=[],
        risk_management=risk_management,
    )
