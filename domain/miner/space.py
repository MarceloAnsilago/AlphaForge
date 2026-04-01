from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MinerFilterConfig:
    min_trades: int = 5
    min_net_profit: float = 0.0
    max_drawdown: float = 1_000.0
    min_profit_factor: float = 1.1


@dataclass(slots=True)
class MinerEvaluationConfig:
    mode: str = "simple"
    split_method: str = "single_split"
    train_ratio: float = 0.7
    test_ratio: float = 0.2
    walk_forward_step_ratio: float | None = None
    minimum_partition_size: int = 20
    minimum_window_pass_rate: float = 1.0
    max_walk_forward_windows: int | None = None
    expanding_train: bool = True
    dataset_id: str = "primary"
    additional_datasets: list[dict[str, Any]] = field(default_factory=list)
    walk_forward_windows: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class MinerSearchSpace:
    indicators: list[str]
    operators: list[str]
    max_rules_per_strategy: int
    directions: list[str]
    market: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=lambda: {"initial_volume": 1.0, "backtest": {"fixed_spread": 0.0}})
    risk_management: dict[str, Any] = field(
        default_factory=lambda: {
            "stop": {"type": "NONE", "value": 0.0},
            "take": {"type": "NONE", "value": 0.0},
        }
    )
    connectors: list[str] = field(default_factory=lambda: ["E", "OU"])
    template_families: list[str] = field(default_factory=lambda: ["price_vs_ma", "ma_crossover", "rsi_level", "macd_cross", "bbands_reversion"])
    period_ranges: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {
            "ma_period": (5, 50),
            "fast_ma_period": (3, 20),
            "slow_ma_period": (10, 80),
            "rsi_period": (5, 30),
            "bbands_period": (10, 40),
        }
    )
    float_ranges: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "bbands_deviation": (1.5, 3.0),
            "oversold_level": (20.0, 45.0),
            "overbought_level": (55.0, 80.0),
        }
    )
    filters: MinerFilterConfig = field(default_factory=MinerFilterConfig)
    evaluation: MinerEvaluationConfig = field(default_factory=MinerEvaluationConfig)


def default_search_space(
    *,
    symbol: str | None,
    timeframe: str | None,
    max_rules_per_strategy: int = 2,
    initial_volume: float = 1.0,
    fixed_spread: float = 0.0,
    filters: MinerFilterConfig | None = None,
    evaluation: MinerEvaluationConfig | None = None,
) -> MinerSearchSpace:
    return MinerSearchSpace(
        indicators=["SMA", "EMA", "RSI", "MACD", "Bandas de Bollinger"],
        operators=[
            "GREATER_THAN",
            "LESS_THAN",
            "CROSS_UP",
            "CROSS_DOWN",
            "GREATER_OR_EQUAL",
            "LESS_OR_EQUAL",
        ],
        max_rules_per_strategy=max_rules_per_strategy,
        directions=["BUY", "SELL"],
        market={
            "symbol": symbol,
            "timeframe": timeframe,
            "quote_period": "FULL_HISTORY",
        },
        settings={
            "initial_volume": initial_volume,
            "backtest": {"fixed_spread": fixed_spread},
        },
        filters=filters or MinerFilterConfig(),
        evaluation=evaluation or MinerEvaluationConfig(),
    )
