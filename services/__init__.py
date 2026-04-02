from __future__ import annotations

from importlib import import_module

__all__ = [
    "BacktestService",
    "MinerService",
    "MiningCampaignService",
    "StrategyService",
    "connect_terminal",
    "get_service_error",
    "load_market_data",
    "load_terminal_symbols",
]


def __getattr__(name: str):
    mapping = {
        "BacktestService": ("services.backtest_service", "BacktestService"),
        "MinerService": ("services.miner_service", "MinerService"),
        "MiningCampaignService": ("services.mining_campaign_service", "MiningCampaignService"),
        "StrategyService": ("services.strategy_service", "StrategyService"),
        "connect_terminal": ("services.mt5_service", "connect_terminal"),
        "get_service_error": ("services.mt5_service", "get_service_error"),
        "load_market_data": ("services.mt5_service", "load_market_data"),
        "load_terminal_symbols": ("services.mt5_service", "load_terminal_symbols"),
    }
    if name not in mapping:
        raise AttributeError(name)
    module_name, attr_name = mapping[name]
    module = import_module(module_name)
    return getattr(module, attr_name)
