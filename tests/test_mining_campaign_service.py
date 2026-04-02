from __future__ import annotations

import unittest

import pandas as pd

from domain.miner.pipeline import MinerPipeline
from domain.miner.space import MinerEvaluationConfig, MinerFilterConfig, default_search_space
from domain.strategy.normalizer import build_strategy_draft
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


def _walk_forward_candles() -> pd.DataFrame:
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


def _sell_candidate(name: str, threshold: float) -> dict:
    return build_strategy_draft(
        name=name,
        direction="SELL",
        settings={"initial_volume": 1.0, "backtest": {"fixed_spread": 0.0}},
        market={"symbol": "EURUSD", "timeframe": "M5", "quote_period": "FULL_HISTORY"},
        entry_rules=[
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "GREATER_THAN",
                "source_b": {"source_type": "fixed", "value": threshold},
                "metadata": {"side": "SELL"},
            }
        ],
        exit_rules=[
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "LESS_THAN",
                "source_b": {"source_type": "fixed", "value": threshold},
                "metadata": {"side": "SELL"},
            }
        ],
        risk_management={"stop": {"type": "NONE", "value": 0.0}, "take": {"type": "NONE", "value": 0.0}},
    ).to_dict()


class MiningCampaignServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = InMemoryDatabaseClient()
        self.strategy_repository = StrategyRepository(self.db)
        self.backtest_repository = BacktestRepository(self.db)
        self.mining_campaign_repository = MiningCampaignRepository(self.db)
        self.strategy_service = StrategyService(self.strategy_repository)
        self.backtest_service = BacktestService(self.backtest_repository)
        self.mining_campaign_service = MiningCampaignService(
            mining_campaign_repository=self.mining_campaign_repository,
            backtest_repository=self.backtest_repository,
        )
        self.miner_service = MinerService(
            strategy_service=self.strategy_service,
            backtest_service=self.backtest_service,
            strategy_repository=self.strategy_repository,
            backtest_repository=self.backtest_repository,
            mining_campaign_service=self.mining_campaign_service,
        )

    def test_create_campaign_persists_metadata(self) -> None:
        search_space = default_search_space(
            symbol="EURUSD",
            timeframe="M5",
            filters=MinerFilterConfig(min_trades=0, min_net_profit=-999.0, max_drawdown=9999.0, min_profit_factor=0.0),
        )
        campaign = self.mining_campaign_service.ensure_campaign(
            campaign_id="campaign-alpha",
            name="Campaign Alpha",
            evaluation=search_space.evaluation,
            search_space=search_space,
            quantity=12,
            seed=7,
            execution_parameters={"fill_policy": "next_candle_open"},
        )

        self.assertEqual(campaign["id"], "campaign-alpha")
        self.assertEqual(campaign["name"], "Campaign Alpha")
        self.assertEqual(campaign["evaluation_mode"], "simple")
        self.assertEqual(campaign["dataset_id"], "primary")
        self.assertEqual(campaign["status"], "running")

    def test_mine_batch_links_runs_to_campaign(self) -> None:
        result = self.miner_service.mine_batch(
            candles=_candles(),
            quantity=3,
            symbol="EURUSD",
            timeframe="M5",
            seed=9,
            top_k=2,
            max_rules_per_strategy=1,
            filters=MinerFilterConfig(min_trades=0, min_net_profit=-999.0, max_drawdown=9999.0, min_profit_factor=0.0),
        )

        campaign_id = result["campaign"]["id"]
        campaign = self.mining_campaign_repository.get_campaign(campaign_id)
        persisted_runs = self.backtest_repository.list_runs_by_campaign(campaign_id)

        self.assertIsNotNone(campaign)
        self.assertEqual(campaign["status"], "completed")
        self.assertEqual(campaign["configuration"]["batch_summary"]["processed"], 3)
        self.assertTrue(persisted_runs)
        self.assertEqual({row["campaign_id"] for row in persisted_runs}, {campaign_id})

    def test_list_top_strategies_by_campaign_returns_ranked_results(self) -> None:
        evaluation = MinerEvaluationConfig(mode="simple")
        search_space = default_search_space(
            symbol="EURUSD",
            timeframe="M5",
            filters=MinerFilterConfig(min_trades=0, min_net_profit=-999.0, max_drawdown=9999.0, min_profit_factor=0.0),
            evaluation=evaluation,
        )
        campaign = self.mining_campaign_service.ensure_campaign(
            campaign_id="campaign-top",
            name="Top Campaign",
            evaluation=evaluation,
            search_space=search_space,
            quantity=2,
            seed=11,
            execution_parameters={"fill_policy": "next_candle_open"},
        )
        pipeline = MinerPipeline(
            strategy_service=self.strategy_service,
            backtest_service=self.backtest_service,
            strategy_repository=self.strategy_repository,
            backtest_repository=self.backtest_repository,
            filters=search_space.filters,
            execution_parameters={"fill_policy": "next_candle_open", "campaign_id": campaign["id"]},
            evaluation=evaluation,
        )

        first = pipeline.process_candidate(_sell_candidate("Candidate A", 1.1), _candles())
        second = pipeline.process_candidate(_sell_candidate("Candidate B", 1.5), _candles())
        self.assertEqual(first.status, "accepted")
        self.assertEqual(second.status, "accepted")

        top_strategies = self.mining_campaign_service.list_campaign_top_strategies(campaign["id"], limit=2)

        self.assertEqual(len(top_strategies), 2)
        self.assertEqual({item["campaign_id"] for item in top_strategies}, {campaign["id"]})
        self.assertGreaterEqual(top_strategies[0]["score"], top_strategies[1]["score"])

    def test_list_window_performance_by_campaign_aggregates_windows(self) -> None:
        evaluation = MinerEvaluationConfig(
            mode="robust_walk_forward",
            train_ratio=1 / 3,
            test_ratio=1 / 3,
            minimum_partition_size=5,
        )
        search_space = default_search_space(
            symbol="EURUSD",
            timeframe="M5",
            filters=MinerFilterConfig(min_trades=0, min_net_profit=-999.0, max_drawdown=9999.0, min_profit_factor=0.0),
            evaluation=evaluation,
        )
        campaign = self.mining_campaign_service.ensure_campaign(
            campaign_id="campaign-window",
            name="Window Campaign",
            evaluation=evaluation,
            search_space=search_space,
            quantity=1,
            seed=13,
            execution_parameters={"fill_policy": "next_candle_open"},
        )
        pipeline = MinerPipeline(
            strategy_service=self.strategy_service,
            backtest_service=self.backtest_service,
            strategy_repository=self.strategy_repository,
            backtest_repository=self.backtest_repository,
            filters=search_space.filters,
            execution_parameters={"fill_policy": "next_candle_open", "campaign_id": campaign["id"]},
            evaluation=evaluation,
        )

        result = pipeline.process_candidate(_sell_candidate("WF Candidate", 1.15), _walk_forward_candles())
        self.assertEqual(result.status, "accepted")

        performance = self.mining_campaign_service.list_campaign_window_performance(campaign["id"])
        self.assertEqual(len(performance), 4)

        second_window_test = [
            item for item in performance if item["window_index"] == 1 and item["dataset_role"] == "test"
        ][0]
        self.assertEqual(second_window_test["campaign_id"], campaign["id"])
        self.assertGreaterEqual(second_window_test["pass_rate"], 0.0)
        self.assertIn("average_stability", second_window_test)


if __name__ == "__main__":
    unittest.main()
