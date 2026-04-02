from __future__ import annotations

import unittest

import pandas as pd

from core.backtest_engine import run_backtest
from domain.miner.scoring import score_train_test_results, score_walk_forward_results
from domain.miner.generator import RandomStrategyGenerator
from domain.miner.pipeline import MinerPipeline
from domain.miner.space import MinerEvaluationConfig, MinerFilterConfig, default_search_space
from domain.strategy.normalizer import build_strategy_draft, normalize_strategy
from infra.db.supabase_client import InMemoryDatabaseClient
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.mining_campaign_repository import MiningCampaignRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.backtest_service import BacktestService
from services.miner_service import MinerService
from services.mining_campaign_service import MiningCampaignService
from services.strategy_service import StrategyService


def _candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-01-01", periods=5, freq="h"),
            "open": [1.0, 1.1, 1.2, 1.1, 1.0],
            "high": [1.1, 2.1, 3.1, 2.1, 1.1],
            "low": [0.9, 1.0, 1.1, 1.0, 0.9],
            "close": [1.0, 2.0, 3.0, 2.0, 1.0],
            "tick_volume": [10, 10, 10, 10, 10],
        }
    )


def _profitable_sell_candidate():
    return build_strategy_draft(
        name="Sell Candidate",
        direction="SELL",
        settings={"initial_volume": 1.0, "backtest": {"fixed_spread": 0.0}},
        market={"symbol": "EURUSD", "timeframe": "M5", "quote_period": "FULL_HISTORY"},
        entry_rules=[
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "GREATER_THAN",
                "source_b": {"source_type": "fixed", "value": 1.5},
                "metadata": {"side": "SELL"},
            }
        ],
        exit_rules=[
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "LESS_THAN",
                "source_b": {"source_type": "fixed", "value": 1.5},
                "metadata": {"side": "SELL"},
            }
        ],
        risk_management={"stop": {"type": "NONE", "value": 0.0}, "take": {"type": "NONE", "value": 0.0}},
    )


def _overfit_buy_candidate():
    return build_strategy_draft(
        name="Overfit Buy Candidate",
        direction="BUY",
        settings={"initial_volume": 1.0, "backtest": {"fixed_spread": 0.0}},
        market={"symbol": "EURUSD", "timeframe": "M5", "quote_period": "FULL_HISTORY"},
        entry_rules=[
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "GREATER_THAN",
                "source_b": {"source_type": "fixed", "value": 1.3},
                "metadata": {"side": "BUY"},
            }
        ],
        exit_rules=[
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "LESS_THAN",
                "source_b": {"source_type": "fixed", "value": 1.3},
                "metadata": {"side": "BUY"},
            }
        ],
        risk_management={"stop": {"type": "NONE", "value": 0.0}, "take": {"type": "NONE", "value": 0.0}},
    )


def _robust_sell_candidate():
    return build_strategy_draft(
        name="Robust Sell Candidate",
        direction="SELL",
        settings={"initial_volume": 1.0, "backtest": {"fixed_spread": 0.0}},
        market={"symbol": "EURUSD", "timeframe": "M5", "quote_period": "FULL_HISTORY"},
        entry_rules=[
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "GREATER_THAN",
                "source_b": {"source_type": "fixed", "value": 1.15},
                "metadata": {"side": "SELL"},
            }
        ],
        exit_rules=[
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "LESS_THAN",
                "source_b": {"source_type": "fixed", "value": 1.15},
                "metadata": {"side": "SELL"},
            }
        ],
        risk_management={"stop": {"type": "NONE", "value": 0.0}, "take": {"type": "NONE", "value": 0.0}},
    )


def _overfit_candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-02-01", periods=8, freq="h"),
            "open": [1.0, 1.1, 1.2, 1.3, 1.6, 1.5, 1.4, 1.3],
            "high": [1.1, 1.2, 1.3, 1.7, 1.7, 1.6, 1.5, 1.4],
            "low": [0.9, 1.0, 1.1, 1.2, 1.4, 1.3, 1.2, 1.1],
            "close": [1.0, 1.2, 1.4, 1.6, 1.5, 1.4, 1.3, 1.2],
            "tick_volume": [10, 10, 10, 10, 10, 10, 10, 10],
        }
    )


def _robust_candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-03-01", periods=10, freq="h"),
            "open": [1.0, 1.1, 1.2, 1.3, 1.1, 1.0, 1.1, 1.2, 1.3, 1.1],
            "high": [1.1, 1.2, 1.3, 1.4, 1.2, 1.1, 1.2, 1.3, 1.4, 1.2],
            "low": [0.9, 1.0, 1.1, 1.2, 1.0, 0.9, 1.0, 1.1, 1.2, 1.0],
            "close": [1.0, 1.2, 1.4, 1.1, 1.0, 1.0, 1.2, 1.4, 1.1, 1.0],
            "tick_volume": [10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
        }
    )


def _walk_forward_consistent_candles() -> pd.DataFrame:
    chunk = {
        "open": [1.0, 1.1, 1.2, 1.3, 1.1],
        "high": [1.1, 1.2, 1.3, 1.4, 1.2],
        "low": [0.9, 1.0, 1.1, 1.2, 1.0],
        "close": [1.0, 1.2, 1.4, 1.1, 1.0],
    }
    repeats = 3
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-04-01", periods=5 * repeats, freq="h"),
            "open": chunk["open"] * repeats,
            "high": chunk["high"] * repeats,
            "low": chunk["low"] * repeats,
            "close": chunk["close"] * repeats,
            "tick_volume": [10] * (5 * repeats),
        }
    )


def _walk_forward_unstable_candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-05-01", periods=15, freq="h"),
            "open": [
                1.0,
                1.1,
                1.2,
                1.3,
                1.4,
                1.0,
                1.1,
                1.2,
                1.3,
                1.4,
                1.6,
                1.5,
                1.4,
                1.3,
                1.2,
            ],
            "high": [
                1.1,
                1.2,
                1.3,
                1.5,
                1.6,
                1.1,
                1.2,
                1.3,
                1.5,
                1.6,
                1.7,
                1.6,
                1.5,
                1.4,
                1.3,
            ],
            "low": [
                0.9,
                1.0,
                1.1,
                1.2,
                1.3,
                0.9,
                1.0,
                1.1,
                1.2,
                1.3,
                1.4,
                1.3,
                1.2,
                1.1,
                1.0,
            ],
            "close": [
                1.0,
                1.2,
                1.4,
                1.6,
                1.5,
                1.0,
                1.2,
                1.4,
                1.6,
                1.5,
                1.5,
                1.4,
                1.3,
                1.2,
                1.1,
            ],
            "tick_volume": [10] * 15,
        }
    )


class MinerPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        db = InMemoryDatabaseClient()
        strategy_repository = StrategyRepository(db)
        backtest_repository = BacktestRepository(db)
        mining_campaign_repository = MiningCampaignRepository(db)
        strategy_service = StrategyService(strategy_repository)
        backtest_service = BacktestService(backtest_repository)
        mining_campaign_service = MiningCampaignService(
            mining_campaign_repository=mining_campaign_repository,
            backtest_repository=backtest_repository,
        )
        self.pipeline = MinerPipeline(
            strategy_service=strategy_service,
            backtest_service=backtest_service,
            strategy_repository=strategy_repository,
            backtest_repository=backtest_repository,
            filters=MinerFilterConfig(min_trades=1, min_net_profit=0.0, max_drawdown=100.0, min_profit_factor=1.0),
            execution_parameters={"fill_policy": "next_candle_open"},
        )
        self.db = db
        self.strategy_repository = strategy_repository
        self.mining_campaign_service = mining_campaign_service

    def test_random_generator_is_reproducible_and_normalizable(self) -> None:
        search_space = default_search_space(symbol="EURUSD", timeframe="M5", max_rules_per_strategy=2)
        generator_one = RandomStrategyGenerator(search_space=search_space, seed=7)
        generator_two = RandomStrategyGenerator(search_space=search_space, seed=7)

        draft_one = generator_one.generate(1).to_dict()
        draft_two = generator_two.generate(1).to_dict()

        self.assertEqual(draft_one, draft_two)
        spec = normalize_strategy(draft_one)
        self.assertEqual(spec.market["symbol"], "EURUSD")

    def test_pipeline_persists_and_deduplicates_candidate(self) -> None:
        first = self.pipeline.process_candidate(_profitable_sell_candidate(), _candles())
        second = self.pipeline.process_candidate(_profitable_sell_candidate(), _candles())

        self.assertEqual(first.status, "accepted")
        self.assertTrue(first.persisted)
        self.assertIsNotNone(first.backtest_run_id)
        self.assertEqual(second.status, "duplicate_in_batch")

        new_pipeline = MinerPipeline(
            strategy_service=self.pipeline.strategy_service,
            backtest_service=self.pipeline.backtest_service,
            strategy_repository=self.pipeline.strategy_repository,
            backtest_repository=self.pipeline.backtest_repository,
            filters=self.pipeline.filters,
            execution_parameters=self.pipeline.execution_parameters,
        )
        third = new_pipeline.process_candidate(_profitable_sell_candidate(), _candles())
        self.assertEqual(third.status, "duplicate_persisted")

    def test_robust_pipeline_filters_overfit_candidate_on_test_split(self) -> None:
        robust_pipeline = MinerPipeline(
            strategy_service=self.pipeline.strategy_service,
            backtest_service=self.pipeline.backtest_service,
            strategy_repository=self.pipeline.strategy_repository,
            backtest_repository=self.pipeline.backtest_repository,
            filters=MinerFilterConfig(min_trades=1, min_net_profit=0.0, max_drawdown=100.0, min_profit_factor=0.0),
            execution_parameters={"fill_policy": "next_candle_open"},
            evaluation=MinerEvaluationConfig(mode="robust", train_ratio=0.5, minimum_partition_size=4),
        )

        result = robust_pipeline.process_candidate(_overfit_buy_candidate(), _overfit_candles())

        self.assertEqual(result.status, "filtered")
        self.assertEqual(result.evaluation_mode, "robust")
        self.assertIsNotNone(result.train_backtest_run_id)
        self.assertIsNotNone(result.test_backtest_run_id)
        self.assertEqual(result.rejection_reason, "test:net_profit")
        self.assertLess(result.score_breakdown.overfit_penalty, 1.0)
        self.assertIsNotNone(result.score_breakdown.test_metrics)
        self.assertLess(result.score_breakdown.test_metrics.net_profit, 0.0)

    def test_robust_scoring_ranks_consistent_strategy_above_overfit_one(self) -> None:
        filters = MinerFilterConfig(min_trades=1, min_net_profit=0.0, max_drawdown=100.0, min_profit_factor=0.0)

        robust_spec = normalize_strategy(_robust_sell_candidate())
        robust_frame = _robust_candles()
        robust_train = run_backtest(robust_spec, robust_frame.iloc[:5].reset_index(drop=True))
        robust_test = run_backtest(robust_spec, robust_frame.iloc[5:].reset_index(drop=True))
        robust_score = score_train_test_results(robust_train, robust_test, filters)

        overfit_spec = normalize_strategy(_overfit_buy_candidate())
        overfit_frame = _overfit_candles()
        overfit_train = run_backtest(overfit_spec, overfit_frame.iloc[:4].reset_index(drop=True))
        overfit_test = run_backtest(overfit_spec, overfit_frame.iloc[4:].reset_index(drop=True))
        overfit_score = score_train_test_results(overfit_train, overfit_test, filters)

        self.assertTrue(robust_score.passed_filters)
        self.assertFalse(overfit_score.passed_filters)
        self.assertGreater(robust_score.score, overfit_score.score)
        self.assertGreater(robust_score.consistency, overfit_score.consistency)

    def test_walk_forward_with_single_configured_window(self) -> None:
        walk_forward_pipeline = MinerPipeline(
            strategy_service=self.pipeline.strategy_service,
            backtest_service=self.pipeline.backtest_service,
            strategy_repository=self.pipeline.strategy_repository,
            backtest_repository=self.pipeline.backtest_repository,
            filters=MinerFilterConfig(min_trades=1, min_net_profit=0.0, max_drawdown=100.0, min_profit_factor=0.0),
            execution_parameters={"fill_policy": "next_candle_open"},
            evaluation=MinerEvaluationConfig(
                mode="robust_walk_forward",
                minimum_partition_size=5,
                walk_forward_windows=[
                    {"label": "wf_0", "train_start": 0, "train_end": 4, "test_start": 5, "test_end": 9}
                ],
            ),
        )

        result = walk_forward_pipeline.process_candidate(_robust_sell_candidate(), _walk_forward_consistent_candles())

        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.evaluation_mode, "robust_walk_forward")
        self.assertEqual(len(result.window_backtest_run_ids), 2)
        self.assertEqual(result.score_breakdown.walk_forward_metrics.total_windows, 1)
        self.assertEqual(result.score_breakdown.walk_forward_metrics.window_pass_rate, 1.0)

    def test_walk_forward_builds_multiple_windows_and_persists_runs(self) -> None:
        walk_forward_pipeline = MinerPipeline(
            strategy_service=self.pipeline.strategy_service,
            backtest_service=self.pipeline.backtest_service,
            strategy_repository=self.pipeline.strategy_repository,
            backtest_repository=self.pipeline.backtest_repository,
            filters=MinerFilterConfig(min_trades=1, min_net_profit=0.0, max_drawdown=100.0, min_profit_factor=0.0),
            execution_parameters={"fill_policy": "next_candle_open"},
            evaluation=MinerEvaluationConfig(
                mode="robust_walk_forward",
                train_ratio=1 / 3,
                test_ratio=1 / 3,
                minimum_partition_size=5,
            ),
        )

        result = walk_forward_pipeline.process_candidate(_robust_sell_candidate(), _walk_forward_consistent_candles())

        self.assertEqual(result.status, "accepted")
        self.assertEqual(len(result.window_backtest_run_ids), 4)
        self.assertEqual(result.score_breakdown.walk_forward_metrics.total_windows, 2)
        self.assertEqual(result.score_breakdown.walk_forward_metrics.approved_windows, 2)
        self.assertGreater(result.score, 0.0)
        persisted_runs = [row for row in self.db.tables.get("backtest_runs", []) if row["id"] in result.window_backtest_run_ids]
        self.assertEqual(len(persisted_runs), 4)
        self.assertEqual({row["dataset_role"] for row in persisted_runs}, {"train", "test"})
        self.assertEqual({row["evaluation_mode"] for row in persisted_runs}, {"robust_walk_forward"})
        self.assertEqual({row["campaign_id"] for row in persisted_runs}, {"primary:robust_walk_forward"})

    def test_walk_forward_filters_strategy_that_only_works_in_one_window(self) -> None:
        walk_forward_pipeline = MinerPipeline(
            strategy_service=self.pipeline.strategy_service,
            backtest_service=self.pipeline.backtest_service,
            strategy_repository=self.pipeline.strategy_repository,
            backtest_repository=self.pipeline.backtest_repository,
            filters=MinerFilterConfig(min_trades=1, min_net_profit=0.0, max_drawdown=100.0, min_profit_factor=0.0),
            execution_parameters={"fill_policy": "next_candle_open"},
            evaluation=MinerEvaluationConfig(
                mode="robust_walk_forward",
                train_ratio=1 / 3,
                test_ratio=1 / 3,
                minimum_partition_size=5,
                minimum_window_pass_rate=1.0,
            ),
        )

        result = walk_forward_pipeline.process_candidate(_overfit_buy_candidate(), _walk_forward_unstable_candles())

        self.assertEqual(result.status, "filtered")
        self.assertTrue(result.rejection_reason.startswith("walk_forward:"))
        self.assertEqual(result.score_breakdown.walk_forward_metrics.total_windows, 2)
        self.assertEqual(result.score_breakdown.walk_forward_metrics.approved_windows, 1)
        self.assertLess(result.score_breakdown.walk_forward_metrics.window_pass_rate, 1.0)

    def test_walk_forward_scoring_ranks_consistent_strategy_above_unstable_one(self) -> None:
        filters = MinerFilterConfig(min_trades=1, min_net_profit=0.0, max_drawdown=100.0, min_profit_factor=0.0)

        consistent_spec = normalize_strategy(_robust_sell_candidate())
        consistent_frame = _walk_forward_consistent_candles()
        consistent_windows = [
            (
                run_backtest(consistent_spec, consistent_frame.iloc[:5].reset_index(drop=True)),
                run_backtest(consistent_spec, consistent_frame.iloc[5:10].reset_index(drop=True)),
                "window_0",
            ),
            (
                run_backtest(consistent_spec, consistent_frame.iloc[:10].reset_index(drop=True)),
                run_backtest(consistent_spec, consistent_frame.iloc[10:15].reset_index(drop=True)),
                "window_1",
            ),
        ]
        consistent_score = score_walk_forward_results(consistent_windows, filters, minimum_window_pass_rate=1.0)

        unstable_spec = normalize_strategy(_overfit_buy_candidate())
        unstable_frame = _walk_forward_unstable_candles()
        unstable_windows = [
            (
                run_backtest(unstable_spec, unstable_frame.iloc[:5].reset_index(drop=True)),
                run_backtest(unstable_spec, unstable_frame.iloc[5:10].reset_index(drop=True)),
                "window_0",
            ),
            (
                run_backtest(unstable_spec, unstable_frame.iloc[:10].reset_index(drop=True)),
                run_backtest(unstable_spec, unstable_frame.iloc[10:15].reset_index(drop=True)),
                "window_1",
            ),
        ]
        unstable_score = score_walk_forward_results(unstable_windows, filters, minimum_window_pass_rate=1.0)

        self.assertTrue(consistent_score.passed_filters)
        self.assertFalse(unstable_score.passed_filters)
        self.assertGreater(consistent_score.score, unstable_score.score)
        self.assertGreater(
            consistent_score.walk_forward_metrics.stability_between_windows,
            unstable_score.walk_forward_metrics.stability_between_windows,
        )
        self.assertGreater(consistent_score.walk_forward_metrics.window_pass_rate, unstable_score.walk_forward_metrics.window_pass_rate)

    def test_miner_service_runs_batch(self) -> None:
        miner_service = MinerService(
            strategy_service=self.pipeline.strategy_service,
            backtest_service=self.pipeline.backtest_service,
            strategy_repository=self.pipeline.strategy_repository,
            backtest_repository=self.pipeline.backtest_repository,
            mining_campaign_service=self.mining_campaign_service,
        )
        result = miner_service.mine_batch(
            candles=_candles(),
            quantity=3,
            symbol="EURUSD",
            timeframe="M5",
            seed=9,
            top_k=2,
            max_rules_per_strategy=1,
            filters=MinerFilterConfig(min_trades=0, min_net_profit=-999.0, max_drawdown=9999.0, min_profit_factor=0.0),
        )

        self.assertEqual(result["summary"]["processed"], 3)
        self.assertEqual(len(result["results"]), 3)


if __name__ == "__main__":
    unittest.main()
