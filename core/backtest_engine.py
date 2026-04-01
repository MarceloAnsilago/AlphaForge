from __future__ import annotations

from typing import Any

import pandas as pd

from core.backtest.engine import BacktestEngine


def run_backtest(strategy: dict[str, Any], candles: pd.DataFrame) -> dict[str, Any]:
    engine = BacktestEngine()
    result = engine.run(strategy, candles)
    return {
        **result,
        "signals": {
            "entry": result["signals"]["entry_signals"],
            "exit": result["signals"]["exit_signals"],
        },
    }
