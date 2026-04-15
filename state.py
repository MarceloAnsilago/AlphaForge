from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _build_default_state() -> dict[str, Any]:
    return {
        "ui_page": "Builder",
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
        "show_market_chart": False,
        "saved_strategy": None,
        "builder_last_payload": None,
        "builder_last_backtest": None,
        "builder_attempts": [],
        "builder_attempt_counter": 0,
        "builder_selected_attempt_id": None,
    }


def get_state() -> dict[str, Any]:
    for key, value in _build_default_state().items():
        if key not in st.session_state:
            st.session_state[key] = value
    return st.session_state
