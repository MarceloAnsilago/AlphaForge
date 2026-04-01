from __future__ import annotations

import unittest

import pandas as pd

from domain.miner.generator import RandomStrategyGenerator
from domain.miner.pipeline import MinerPipeline
from domain.miner.space import MinerFilterConfig, default_search_space
from domain.strategy.normalizer import build_strategy_draft, normalize_strategy
from infra.db.supabase_client import InMemoryDatabaseClient
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.backtest_service import BacktestService
from services.miner_service import MinerService
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


class MinerPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        db = InMemoryDatabaseClient()
        strategy_repository = StrategyRepository(db)
        backtest_repository = BacktestRepository(db)
        strategy_service = StrategyService(strategy_repository)
        backtest_service = BacktestService(backtest_repository)
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

    def test_miner_service_runs_batch(self) -> None:
        miner_service = MinerService(
            strategy_service=self.pipeline.strategy_service,
            backtest_service=self.pipeline.backtest_service,
            strategy_repository=self.pipeline.strategy_repository,
            backtest_repository=self.pipeline.backtest_repository,
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
