from __future__ import annotations

from copy import deepcopy
from typing import Any
import uuid

import pandas as pd
from flask import session


_STATE_STORE: dict[str, dict[str, Any]] = {}


def _default_state() -> dict[str, Any]:
    return {
        "selected_campaign_id": None,
        "selected_strategy_version_id": None,
        "selected_backtest_run_id": None,
        "selected_strategy_run_ids": [],
        "selected_strategy_position": 0,
        "mt5_connected": False,
        "mt5_status": "",
        "symbols_status": "",
        "symbols": [],
        "market_data": pd.DataFrame(),
        "market_query": None,
        "saved_strategy": None,
        "builder_form": {},
        "builder_payload": None,
        "builder_backtest": None,
    }


def get_runtime_state() -> dict[str, Any]:
    client_id = session.get("_alphaforge_client_id")
    if not client_id:
        client_id = str(uuid.uuid4())
        session["_alphaforge_client_id"] = client_id

    if client_id not in _STATE_STORE:
        _STATE_STORE[client_id] = _default_state()

    state = _STATE_STORE[client_id]
    for key, value in _default_state().items():
        if key not in state:
            state[key] = deepcopy(value)
    return state
