from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - depends on local environment
    mt5 = None


_LAST_ERROR = ""

_TIMEFRAME_MAP = {
    "M1": "TIMEFRAME_M1",
    "M2": "TIMEFRAME_M2",
    "M3": "TIMEFRAME_M3",
    "M4": "TIMEFRAME_M4",
    "M5": "TIMEFRAME_M5",
    "M6": "TIMEFRAME_M6",
    "M10": "TIMEFRAME_M10",
    "M12": "TIMEFRAME_M12",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H2": "TIMEFRAME_H2",
    "H3": "TIMEFRAME_H3",
    "H4": "TIMEFRAME_H4",
    "H6": "TIMEFRAME_H6",
    "H8": "TIMEFRAME_H8",
    "H12": "TIMEFRAME_H12",
    "D1": "TIMEFRAME_D1",
    "W1": "TIMEFRAME_W1",
    "MN1": "TIMEFRAME_MN1",
}
_TIMEFRAME_MINUTES = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M6": 6,
    "M10": 10,
    "M12": 12,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H2": 120,
    "H3": 180,
    "H4": 240,
    "H6": 360,
    "H8": 480,
    "H12": 720,
    "D1": 1440,
    "W1": 10080,
    "MN1": 43200,
}
_MAX_RANGE_BARS = 20000


def _set_error(message: str) -> None:
    global _LAST_ERROR
    _LAST_ERROR = message


def get_last_error() -> str:
    return _LAST_ERROR


def _mt5_available() -> bool:
    if mt5 is None:
        _set_error(
            "Biblioteca MetaTrader5 nao encontrada. Instale as dependencias antes de abrir o app."
        )
        return False
    return True


def _timeframe_constant(timeframe: str) -> Any:
    if not _mt5_available():
        return None

    constant_name = _TIMEFRAME_MAP.get(timeframe)
    if not constant_name:
        _set_error(f"Timeframe invalido: {timeframe}")
        return None

    return getattr(mt5, constant_name, None)


def _ensure_symbol_selected(symbol: str) -> bool:
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        error = mt5.last_error()
        _set_error(f"Simbolo invalido ou indisponivel no terminal. Detalhes: {error}")
        return False

    if symbol_info.visible:
        return True

    if not mt5.symbol_select(symbol, True):
        error = mt5.last_error()
        _set_error(
            "Nao foi possivel habilitar o simbolo no Market Watch do MetaTrader 5. "
            f"Detalhes: {error}"
        )
        return False

    return True


def _normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=0)


def _estimate_chunk_span(timeframe: str) -> timedelta:
    timeframe_minutes = _TIMEFRAME_MINUTES.get(timeframe, 1440)
    chunk_days = max(1, int((_MAX_RANGE_BARS * timeframe_minutes) / 1440))
    return timedelta(days=chunk_days)


def _copy_rates_range_chunked(
    symbol: str,
    timeframe: str,
    timeframe_constant: Any,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    chunk_span = _estimate_chunk_span(timeframe)
    chunk_start = start
    chunk_frames: list[pd.DataFrame] = []

    while chunk_start < end:
        chunk_end = min(chunk_start + chunk_span, end)
        chunk_rates = mt5.copy_rates_range(
            symbol,
            timeframe_constant,
            chunk_start,
            chunk_end,
        )
        error = mt5.last_error()

        if chunk_rates is None:
            if error[0] == -2 and chunk_span > timedelta(days=1):
                chunk_span = max(timedelta(days=1), timedelta(seconds=int(chunk_span.total_seconds() / 2)))
                continue
            _set_error(
                "Nao foi possivel carregar candles. "
                "Verifique a conexao com o MT5 e se o ativo esta disponivel. "
                f"Detalhes: {error}"
            )
            return pd.DataFrame()

        chunk_frame = pd.DataFrame(chunk_rates)
        if not chunk_frame.empty:
            chunk_frames.append(chunk_frame)

        chunk_start = chunk_end

    if not chunk_frames:
        return pd.DataFrame()

    dataframe = pd.concat(chunk_frames, ignore_index=True)
    return dataframe.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)


def initialize_mt5() -> bool:
    if not _mt5_available():
        return False

    initialized = mt5.initialize()
    if not initialized:
        error = mt5.last_error()
        _set_error(
            "Nao foi possivel conectar ao MetaTrader 5. "
            "Verifique se o terminal esta aberto e logado. "
            f"Detalhes: {error}"
        )
        return False

    _set_error("")
    return True


def get_symbols() -> list[str]:
    if not _mt5_available():
        return []

    symbols = mt5.symbols_get()
    if symbols is None:
        error = mt5.last_error()
        _set_error(
            "Nao foi possivel listar os simbolos do MetaTrader 5. "
            f"Detalhes: {error}"
        )
        return []

    _set_error("")
    return sorted(symbol.name for symbol in symbols)


def build_market_period_range(
    period_mode: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[datetime, datetime] | None:
    now = datetime.now(timezone.utc)

    if period_mode == "LAST_MONTH":
        return now - timedelta(days=30), now
    if period_mode == "LAST_YEAR":
        return now - timedelta(days=365), now
    if period_mode == "FULL_HISTORY":
        return datetime(2000, 1, 1, tzinfo=timezone.utc), now
    if period_mode == "CUSTOM":
        if start_date is None or end_date is None:
            _set_error("Informe as datas inicial e final para o periodo personalizado.")
            return None

        start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        if start > end:
            _set_error("A data inicial nao pode ser maior que a data final.")
            return None
        return start, end

    _set_error(f"Modo de periodo invalido: {period_mode}")
    return None


def get_candles(symbol: str, timeframe: str, n: int = 500) -> pd.DataFrame:
    return get_candles_by_range(symbol, timeframe, bars=n)


def get_candles_by_range(
    symbol: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
    bars: int | None = None,
) -> pd.DataFrame:
    if not _mt5_available():
        return pd.DataFrame()

    timeframe_constant = _timeframe_constant(timeframe)
    if timeframe_constant is None:
        return pd.DataFrame()

    if not _ensure_symbol_selected(symbol):
        return pd.DataFrame()

    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    dataframe = pd.DataFrame()
    if start is not None and end is not None:
        rates = mt5.copy_rates_range(
            symbol,
            timeframe_constant,
            _normalize_utc_datetime(start),
            _normalize_utc_datetime(end),
        )
        if rates is None and mt5.last_error()[0] == -2:
            dataframe = _copy_rates_range_chunked(
                symbol,
                timeframe,
                timeframe_constant,
                _normalize_utc_datetime(start),
                _normalize_utc_datetime(end),
            )
        elif rates is not None:
            dataframe = pd.DataFrame(rates)
    else:
        effective_bars = bars or 500
        rates = mt5.copy_rates_from_pos(symbol, timeframe_constant, 0, effective_bars)
        if rates is not None:
            dataframe = pd.DataFrame(rates)

    if rates is None and dataframe.empty:
        error = mt5.last_error()
        _set_error(
            "Nao foi possivel carregar candles. "
            "Verifique a conexao com o MT5 e se o ativo esta disponivel. "
            f"Detalhes: {error}"
        )
        return pd.DataFrame()

    if dataframe.empty:
        _set_error("Nenhum candle foi retornado pelo MetaTrader 5 para os parametros informados.")
        return dataframe

    dataframe["time"] = pd.to_datetime(dataframe["time"], unit="s", utc=True)
    columns = ["time", "open", "high", "low", "close", "tick_volume"]
    _set_error("")
    return dataframe.loc[:, columns]
