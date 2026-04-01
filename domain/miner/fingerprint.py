from __future__ import annotations

from hashlib import sha256
from typing import Any

import json
import pandas as pd

from domain.strategy.spec import StrategySpec


def stable_json_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def strategy_spec_fingerprint(strategy_spec: StrategySpec) -> str:
    return stable_json_hash(strategy_spec.to_dict())


def candle_frame_fingerprint(candles: pd.DataFrame) -> str:
    if candles.empty:
        return stable_json_hash({"candles": []})

    normalized = candles.copy()
    normalized["time"] = normalized["time"].astype(str)
    return stable_json_hash({"candles": normalized.to_dict(orient="records")})


def backtest_input_fingerprint(
    *,
    strategy_version_id: str,
    strategy_spec: StrategySpec,
    candles: pd.DataFrame,
    execution_parameters: dict[str, Any] | None = None,
) -> str:
    execution_parameters = dict(execution_parameters or {})
    return stable_json_hash(
        {
            "strategy_version_id": strategy_version_id,
            "strategy_fingerprint": strategy_spec_fingerprint(strategy_spec),
            "candle_fingerprint": candle_frame_fingerprint(candles),
            "execution_parameters": execution_parameters,
            "symbol": strategy_spec.market.get("symbol"),
            "timeframe": strategy_spec.market.get("timeframe"),
        }
    )
