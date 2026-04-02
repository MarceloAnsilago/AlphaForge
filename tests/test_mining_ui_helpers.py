from __future__ import annotations

import unittest

from ui.mining_helpers import build_equity_curve_frame, build_walk_forward_frame, filter_strategy_rows, summarize_strategy_rules


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
