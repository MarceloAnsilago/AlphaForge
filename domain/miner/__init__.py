from __future__ import annotations

from importlib import import_module

__all__ = [
    "BacktestMetricSnapshot",
    "MinerEvaluationConfig",
    "MinerFilterConfig",
    "MinerPipeline",
    "MinerPipelineResult",
    "MinerSearchSpace",
    "RandomStrategyGenerator",
    "ScoreBreakdown",
    "WalkForwardAggregateMetrics",
    "WalkForwardWindowScore",
    "backtest_input_fingerprint",
    "candle_frame_fingerprint",
    "default_search_space",
    "score_backtest_result",
    "score_train_test_results",
    "score_walk_forward_results",
    "strategy_spec_fingerprint",
]


def __getattr__(name: str):
    mapping = {
        "BacktestMetricSnapshot": ("domain.miner.scoring", "BacktestMetricSnapshot"),
        "MinerEvaluationConfig": ("domain.miner.space", "MinerEvaluationConfig"),
        "MinerFilterConfig": ("domain.miner.space", "MinerFilterConfig"),
        "MinerSearchSpace": ("domain.miner.space", "MinerSearchSpace"),
        "default_search_space": ("domain.miner.space", "default_search_space"),
        "RandomStrategyGenerator": ("domain.miner.generator", "RandomStrategyGenerator"),
        "MinerPipeline": ("domain.miner.pipeline", "MinerPipeline"),
        "MinerPipelineResult": ("domain.miner.pipeline", "MinerPipelineResult"),
        "ScoreBreakdown": ("domain.miner.scoring", "ScoreBreakdown"),
        "WalkForwardAggregateMetrics": ("domain.miner.scoring", "WalkForwardAggregateMetrics"),
        "WalkForwardWindowScore": ("domain.miner.scoring", "WalkForwardWindowScore"),
        "score_backtest_result": ("domain.miner.scoring", "score_backtest_result"),
        "score_train_test_results": ("domain.miner.scoring", "score_train_test_results"),
        "score_walk_forward_results": ("domain.miner.scoring", "score_walk_forward_results"),
        "strategy_spec_fingerprint": ("domain.miner.fingerprint", "strategy_spec_fingerprint"),
        "candle_frame_fingerprint": ("domain.miner.fingerprint", "candle_frame_fingerprint"),
        "backtest_input_fingerprint": ("domain.miner.fingerprint", "backtest_input_fingerprint"),
    }
    if name not in mapping:
        raise AttributeError(name)
    module_name, attr_name = mapping[name]
    module = import_module(module_name)
    return getattr(module, attr_name)
