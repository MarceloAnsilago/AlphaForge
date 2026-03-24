from __future__ import annotations

from typing import Any

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - depends on local environment
    mt5 = None


_LAST_ERROR = ""

_TIMEFRAME_MAP = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


def _set_error(message: str) -> None:
    global _LAST_ERROR
    _LAST_ERROR = message


def get_last_error() -> str:
    return _LAST_ERROR


def _mt5_available() -> bool:
    if mt5 is None:
        _set_error(
            "Biblioteca MetaTrader5 não encontrada. Instale as dependências antes de abrir o app."
        )
        return False
    return True


def _timeframe_constant(timeframe: str) -> Any:
    if not _mt5_available():
        return None

    constant_name = _TIMEFRAME_MAP.get(timeframe)
    if not constant_name:
        _set_error(f"Timeframe inválido: {timeframe}")
        return None

    return getattr(mt5, constant_name, None)


def initialize_mt5() -> bool:
    if not _mt5_available():
        return False

    initialized = mt5.initialize()
    if not initialized:
        error = mt5.last_error()
        _set_error(
            "Não foi possível conectar ao MetaTrader 5. "
            "Verifique se o terminal está aberto e logado. "
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
            "Não foi possível listar os símbolos do MetaTrader 5. "
            f"Detalhes: {error}"
        )
        return []

    _set_error("")
    return sorted(symbol.name for symbol in symbols)


def get_candles(symbol: str, timeframe: str, n: int = 500) -> pd.DataFrame:
    if not _mt5_available():
        return pd.DataFrame()

    timeframe_constant = _timeframe_constant(timeframe)
    if timeframe_constant is None:
        return pd.DataFrame()

    rates = mt5.copy_rates_from_pos(symbol, timeframe_constant, 0, n)
    if rates is None:
        error = mt5.last_error()
        _set_error(
            "Não foi possível carregar candles. "
            "Verifique a conexão com o MT5 e se o ativo está disponível. "
            f"Detalhes: {error}"
        )
        return pd.DataFrame()

    dataframe = pd.DataFrame(rates)
    if dataframe.empty:
        _set_error("Nenhum candle foi retornado pelo MetaTrader 5 para os parâmetros informados.")
        return dataframe

    dataframe["time"] = pd.to_datetime(dataframe["time"], unit="s")
    columns = ["time", "open", "high", "low", "close", "tick_volume"]
    _set_error("")
    return dataframe.loc[:, columns]
