from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _build_default_state() -> dict[str, Any]:
    return {
        "mt5_connected": False,
        "mt5_status": "",
        "symbols_status": "",
        "symbols": [],
        "market_data": pd.DataFrame(),
        "market_query": None,
        "show_market_chart": False,
        "saved_strategy": None,
    }


def get_state() -> dict[str, Any]:
    for key, value in _build_default_state().items():
        if key not in st.session_state:
            st.session_state[key] = value
    return st.session_state
