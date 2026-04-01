from __future__ import annotations

import unittest

import pandas as pd

from infra.db.supabase_client import InMemoryDatabaseClient
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.backtest_service import BacktestService
from services.strategy_service import StrategyService


def _strategy_payload(threshold: float = 1.5) -> dict:
    return {
        "name": "Persisted Strategy",
        "direction": "BUY",
        "settings": {"initial_volume": 1.0, "backtest": {"fixed_spread": 0.0}},
        "market": {"symbol": "EURUSD", "timeframe": "M5", "quote_period": "FULL_HISTORY"},
        "entry_rules": [
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "GREATER_THAN",
                "source_b": {"source_type": "fixed", "value": threshold},
                "metadata": {"side": "BUY"},
            }
        ],
        "exit_rules": [
            {
                "source_a": {"source_type": "price", "value": "close"},
                "operator": "LESS_THAN",
                "source_b": {"source_type": "fixed", "value": threshold},
                "metadata": {"side": "BUY"},
            }
        ],
        "risk_management": {
            "stop": {"type": "NONE", "value": 0.0},
            "take": {"type": "NONE", "value": 0.0},
        },
    }


def _candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-01-01", periods=5, freq="h"),
            "open": [1.0, 1.1, 1.2, 1.1, 1.0],
            "high": [1.1, 1.3, 1.4, 1.2, 1.1],
            "low": [0.9, 1.0, 1.1, 1.0, 0.9],
            "close": [1.0, 2.0, 3.0, 2.0, 1.0],
            "tick_volume": [10, 10, 10, 10, 10],
        }
    )


class PersistenceServicesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = InMemoryDatabaseClient()
        self.strategy_repository = StrategyRepository(self.db)
        self.backtest_repository = BacktestRepository(self.db)
        self.strategy_service = StrategyService(self.strategy_repository)
        self.backtest_service = BacktestService(self.backtest_repository)

    def test_persist_strategy_spec(self) -> None:
        created = self.strategy_service.create_strategy(_strategy_payload())

        self.assertEqual(created["strategy_version"]["spec_version"], "strategy-spec/1")
        self.assertEqual(created["strategy"]["latest_version_number"], 1)
        self.assertEqual(created["strategy_version"]["spec"]["version"], "strategy-spec/1")

    def test_create_strategy_version(self) -> None:
        created = self.strategy_service.create_strategy(_strategy_payload())
        versioned = self.strategy_service.create_strategy_version(
            created["strategy"]["id"],
            _strategy_payload(threshold=2.5),
        )

        self.assertEqual(versioned["strategy_version"]["version_number"], 2)
        versions = self.strategy_repository.list_strategy_versions(created["strategy"]["id"])
        self.assertEqual(len(versions), 2)

    def test_persist_backtest_run_metrics_and_trades(self) -> None:
        created = self.strategy_service.create_strategy(_strategy_payload())
        execution = self.backtest_service.run_and_persist_backtest(
            strategy_version=created["strategy_version"],
            strategy=created["strategy_spec"],
            candles=_candles(),
            execution_parameters={"fill_policy": "next_candle_open"},
        )

        persistence = execution["persistence"]
        self.assertEqual(persistence["backtest_run"]["strategy_version_id"], created["strategy_version"]["id"])
        self.assertEqual(persistence["backtest_metrics"]["total_trades"], 1)
        self.assertEqual(len(persistence["backtest_trades"]), 1)
        self.assertTrue(persistence["backtest_run"]["input_fingerprint"])

    def test_persist_metrics_without_trades(self) -> None:
        created = self.strategy_service.create_strategy(
            {
                **_strategy_payload(),
                "entry_rules": [],
                "exit_rules": [],
            }
        )
        execution = self.backtest_service.run_and_persist_backtest(
            strategy_version=created["strategy_version"],
            strategy=created["strategy_spec"],
            candles=_candles(),
            execution_parameters={"fill_policy": "next_candle_open"},
        )

        self.assertEqual(execution["persistence"]["backtest_metrics"]["total_trades"], 0)
        self.assertEqual(len(execution["persistence"]["backtest_trades"]), 0)


if __name__ == "__main__":
    unittest.main()
