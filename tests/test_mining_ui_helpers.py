from __future__ import annotations

import unittest

from ui.mining_helpers import (
    build_equity_curve_frame,
    build_walk_forward_frame,
    filter_campaign_rows,
    filter_strategy_rows,
    paginate_rows,
    summarize_strategy_rules,
)


class MiningUiHelpersTests(unittest.TestCase):
    def test_build_equity_curve_frame_accumulates_pnl(self) -> None:
        frame = build_equity_curve_frame(
            [
                {"exit_time": "2026-01-01T00:00:00", "pnl": 10.0},
                {"exit_time": "2026-01-01T01:00:00", "pnl": -4.0},
                {"exit_time": "2026-01-01T02:00:00", "pnl": 3.0},
            ]
        )

        self.assertEqual(list(frame["equity"]), [10.0, 6.0, 9.0])
        self.assertEqual(list(frame["drawdown"]), [0.0, -4.0, -1.0])

    def test_filter_campaign_rows_applies_query_symbol_and_timeframe(self) -> None:
        campaigns = [
            {"id": "c1", "name": "EURUSD WF", "symbol": "EURUSD", "timeframe": "M5"},
            {"id": "c2", "name": "GBPUSD Robust", "symbol": "GBPUSD", "timeframe": "M15"},
            {"id": "c3", "name": "EURUSD Simple", "symbol": "EURUSD", "timeframe": "H1"},
        ]
        summaries = {"c1": {"approved_quantity": 2}, "c2": {"approved_quantity": 1}, "c3": {"approved_quantity": 0}}

        filtered = filter_campaign_rows(
            campaigns,
            summaries,
            query="eurusd",
            symbol="EURUSD",
            timeframe="M5",
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "c1")
        self.assertEqual(filtered[0]["summary"]["approved_quantity"], 2)

    def test_filter_strategy_rows_applies_all_filters(self) -> None:
        rows = [
            {"strategy_name": "Alpha Long", "strategy_direction": "BUY", "status": "top", "score": 80.0},
            {"strategy_name": "Beta Short", "strategy_direction": "SELL", "status": "filtered", "score": 20.0},
            {"strategy_name": "Gamma Long", "strategy_direction": "BUY", "status": "accepted", "score": 55.0},
        ]

        filtered = filter_strategy_rows(
            rows,
            query="long",
            direction="BUY",
            status="accepted",
            minimum_score=50.0,
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["strategy_name"], "Gamma Long")

    def test_paginate_rows_returns_requested_slice(self) -> None:
        rows = [{"id": f"item-{index}"} for index in range(1, 11)]

        page = paginate_rows(rows, page=2, page_size=3)

        self.assertEqual([item["id"] for item in page["items"]], ["item-4", "item-5", "item-6"])
        self.assertEqual(page["total_pages"], 4)
        self.assertEqual(page["start_index"], 3)

    def test_summarize_strategy_rules_returns_readable_text(self) -> None:
        summary = summarize_strategy_rules(
            {
                "entry_rules": [
                    {
                        "source_a": {"source_type": "price", "value": "close"},
                        "operator": "GREATER_THAN",
                        "source_b": {"source_type": "fixed", "value": 1.5},
                        "metadata": {"side": "BUY"},
                    }
                ],
                "exit_rules": [],
            }
        )

        self.assertEqual(summary["entry_rules"][0], "price:close GREATER_THAN fixed:1.5 [BUY]")
        self.assertEqual(summary["exit_rules"], [])

    def test_build_walk_forward_frame_preserves_window_rows(self) -> None:
        frame = build_walk_forward_frame(
            [
                {
                    "window_label": "window_0",
                    "dataset_role": "test",
                    "average_score": 12.0,
                    "pass_rate": 1.0,
                    "average_stability": 0.8,
                }
            ]
        )

        self.assertEqual(frame.iloc[0]["window_label"], "window_0")
        self.assertEqual(frame.iloc[0]["average_stability"], 0.8)


if __name__ == "__main__":
    unittest.main()
