from __future__ import annotations

import unittest

import pandas as pd

from core.backtest.engine import BacktestEngine


def _candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-01-01", periods=5, freq="h"),
            "open": [10.0, 11.0, 12.0, 13.0, 14.0],
            "high": [10.5, 11.5, 12.5, 13.5, 14.5],
            "low": [9.5, 10.5, 11.5, 12.5, 13.5],
            "close": [10.2, 11.2, 12.2, 13.2, 14.2],
        }
    )


def _evaluation_frame(candles: pd.DataFrame) -> pd.DataFrame:
    frame = candles.loc[:, ["time", "close"]].copy()
    frame["entry_signal"] = False
    frame["exit_signal"] = False
    return frame


class BacktestEngineExecutionTests(unittest.TestCase):
    def test_simple_entry_closes_at_end_of_data(self) -> None:
        candles = _candles()

        def signal_evaluator(strategy: dict, market_data: pd.DataFrame) -> dict:
            evaluation = _evaluation_frame(market_data)
            evaluation.loc[0, "entry_signal"] = True
            return {
                "entry_signals": [
                    {
                        "type": "entry",
                        "group_id": "entry_0",
                        "index": 0,
                        "time": market_data.loc[0, "time"],
                        "price": market_data.loc[0, "close"],
                        "side": "BUY",
                        "metadata": {},
                    }
                ],
                "exit_signals": [],
                "evaluation": evaluation,
            }

        engine = BacktestEngine(signal_evaluator=signal_evaluator)
        result = engine.run({"direction": "BUY", "settings": {"initial_volume": 1.0}}, candles)

        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"].iloc[0]
        self.assertEqual(int(trade["entry_index"]), 1)
        self.assertEqual(float(trade["entry_price"]), 11.0)
        self.assertEqual(int(trade["exit_index"]), 4)
        self.assertEqual(trade["exit_reason"], "end_of_data")
        self.assertAlmostEqual(float(result["summary"]["average_return_per_trade"]), 3.2)
        self.assertGreater(float(result["summary"]["profit_factor"]), 0.0)
        self.assertAlmostEqual(float(result["summary"]["expectancy"]), 3.2)
        self.assertEqual(float(result["summary"]["pnl_variance"]), 0.0)

    def test_entry_and_exit_use_next_candle_open_with_spread(self) -> None:
        candles = _candles()

        def signal_evaluator(strategy: dict, market_data: pd.DataFrame) -> dict:
            evaluation = _evaluation_frame(market_data)
            evaluation.loc[0, "entry_signal"] = True
            evaluation.loc[1, "exit_signal"] = True
            return {
                "entry_signals": [
                    {
                        "type": "entry",
                        "group_id": "entry_0",
                        "index": 0,
                        "time": market_data.loc[0, "time"],
                        "price": market_data.loc[0, "close"],
                        "side": "BUY",
                        "metadata": {},
                    }
                ],
                "exit_signals": [
                    {
                        "type": "exit",
                        "group_id": "exit_1",
                        "index": 1,
                        "time": market_data.loc[1, "time"],
                        "price": market_data.loc[1, "close"],
                        "side": "BUY",
                        "metadata": {},
                    }
                ],
                "evaluation": evaluation,
            }

        engine = BacktestEngine(signal_evaluator=signal_evaluator)
        result = engine.run(
            {
                "direction": "BUY",
                "settings": {
                    "initial_volume": 1.0,
                    "backtest": {"fixed_spread": 0.2, "slippage": 0.0},
                },
            },
            candles,
        )

        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"].iloc[0]
        self.assertEqual(int(trade["entry_index"]), 1)
        self.assertEqual(int(trade["exit_index"]), 2)
        self.assertAlmostEqual(float(trade["entry_price"]), 11.1)
        self.assertAlmostEqual(float(trade["exit_price"]), 11.9)
        self.assertAlmostEqual(float(trade["spread_cost"]), 0.2)
        self.assertEqual(trade["exit_reason"], "signal")

    def test_conflict_same_candle_prioritizes_exit_and_rejects_new_entry(self) -> None:
        candles = _candles()

        def signal_evaluator(strategy: dict, market_data: pd.DataFrame) -> dict:
            evaluation = _evaluation_frame(market_data)
            evaluation.loc[0, "entry_signal"] = True
            evaluation.loc[1, ["entry_signal", "exit_signal"]] = True
            return {
                "entry_signals": [
                    {
                        "type": "entry",
                        "group_id": "entry_0",
                        "index": 0,
                        "time": market_data.loc[0, "time"],
                        "price": market_data.loc[0, "close"],
                        "side": "BUY",
                        "metadata": {},
                    },
                    {
                        "type": "entry",
                        "group_id": "entry_1",
                        "index": 1,
                        "time": market_data.loc[1, "time"],
                        "price": market_data.loc[1, "close"],
                        "side": "BUY",
                        "metadata": {},
                    },
                ],
                "exit_signals": [
                    {
                        "type": "exit",
                        "group_id": "exit_1",
                        "index": 1,
                        "time": market_data.loc[1, "time"],
                        "price": market_data.loc[1, "close"],
                        "side": "BUY",
                        "metadata": {},
                    }
                ],
                "evaluation": evaluation,
            }

        engine = BacktestEngine(signal_evaluator=signal_evaluator)
        result = engine.run({"direction": "BUY", "settings": {"initial_volume": 1.0}}, candles)

        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"].iloc[0]
        self.assertEqual(int(trade["entry_index"]), 1)
        self.assertEqual(int(trade["exit_index"]), 2)
        rejected_reasons = [
            event["details"]["reason"]
            for event in result["events"]
            if event["event_type"] == "signal_rejected"
        ]
        self.assertIn("position_already_open", rejected_reasons)

    def test_no_signals_produces_no_trades(self) -> None:
        candles = _candles()

        def signal_evaluator(strategy: dict, market_data: pd.DataFrame) -> dict:
            return {
                "entry_signals": [],
                "exit_signals": [],
                "evaluation": _evaluation_frame(market_data),
            }

        engine = BacktestEngine(signal_evaluator=signal_evaluator)
        result = engine.run({"direction": "BUY", "settings": {"initial_volume": 1.0}}, candles)

        self.assertTrue(result["trades"].empty)
        self.assertEqual(result["summary"]["total_trades"], 0)
        self.assertEqual(len(result["events"]), 0)


if __name__ == "__main__":
    unittest.main()
