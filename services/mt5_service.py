from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from infra.mt5_gateway import (
    build_market_period_range,
    get_candles_by_range,
    get_last_error,
    get_symbols,
    initialize_mt5,
)


def connect_terminal() -> dict[str, Any]:
    connected = initialize_mt5()
    return {
        "connected": connected,
        "status": "Conectado ao MetaTrader 5." if connected else get_last_error(),
    }


def load_terminal_symbols() -> dict[str, Any]:
    symbols = get_symbols()
    error = get_last_error()
    return {
        "symbols": symbols,
        "status": f"{len(symbols)} simbolo(s) carregado(s)." if symbols else (error or "Nenhum simbolo encontrado."),
        "success": bool(symbols),
    }


def load_market_data(
    symbol: str,
    timeframe: str,
    period_mode: str,
    custom_start_date: date | None = None,
    custom_end_date: date | None = None,
) -> dict[str, Any]:
    period_range = build_market_period_range(
        period_mode,
        start_date=custom_start_date,
        end_date=custom_end_date,
    )
    if period_range is None:
        return {
            "data": pd.DataFrame(),
            "query": None,
            "error": get_last_error(),
        }

    start, end = period_range
    candles = get_candles_by_range(
        symbol,
        timeframe,
        start=start,
        end=end,
    )
    return {
        "data": candles,
        "query": {
            "symbol": symbol,
            "timeframe": timeframe,
            "period_mode": period_mode,
            "custom_start_date": custom_start_date.isoformat()
            if custom_start_date is not None
            else None,
            "custom_end_date": custom_end_date.isoformat() if custom_end_date is not None else None,
        },
        "error": get_last_error(),
    }


def get_service_error() -> str:
    return get_last_error()
