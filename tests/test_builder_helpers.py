from __future__ import annotations

from datetime import datetime
import unittest

import pandas as pd

from ui.builder_helpers import (
    build_builder_attempt_record,
    build_builder_attempts_frame,
    build_market_signature,
    resolve_previous_attempt,
    summarize_builder_configuration,
)


class BuilderHelpersTests(unittest.TestCase):
    def test_summarize_builder_configuration_prefers_crossovers(self) -> None:
        label = summarize_builder_configuration(
            "Minha Estrategia",
            {
                "crossovers": {
                    "enabled": True,
                    "fast_source": "Maxima da vela",
                    "slow_source": "Media Movel",
                }
            },
        )

        self.assertEqual(label, "Cruzamento Maxima da vela x Media Movel")

    def test_build_market_signature_uses_query_and_boundaries(self) -> None:
        frame = pd.DataFrame(
            [
                {"time": "2026-04-01T10:00:00Z", "close": 1.0},
                {"time": "2026-04-01T11:00:00Z", "close": 2.0},
            ]
        )

        signature = build_market_signature(frame, {"symbol": "EURUSD", "timeframe": "M5"})

        self.assertEqual(signature["symbol"], "EURUSD")
        self.assertEqual(signature["timeframe"], "M5")
        self.assertEqual(signature["rows"], 2)
        self.assertEqual(signature["first_time"], "2026-04-01T10:00:00Z")
        self.assertEqual(signature["last_time"], "2026-04-01T11:00:00Z")

    def test_build_builder_attempt_record_keeps_metrics_for_history(self) -> None:
        record = build_builder_attempt_record(
            attempt_number=3,
            strategy_name="Minha Estrategia",
            ready_signals={"signal_settings": {"indicator_1": "RSI (Relative Strength Index)"}},
            payload={"name": "payload"},
            backtest_result={
                "summary": {
                    "total_trades": 8,
                    "net_profit": 25.5,
                    "profit_factor": 1.8,
                    "max_drawdown": -4.0,
                    "win_rate": 62.5,
                },
                "ambiguous_entries": 1,
                "performance_curve": pd.DataFrame([{"time": "2026-04-01", "equity": 1.0}]),
                "trades": pd.DataFrame([{"pnl": 1.0}]),
            },
            market_signature={"symbol": "EURUSD", "timeframe": "M5", "rows": 100},
            created_at=datetime(2026, 4, 11, 12, 30, 45),
        )

        self.assertEqual(record["id"], "builder-attempt-003")
        self.assertEqual(record["label"], "Indicadores RSI")
        self.assertEqual(record["created_at"], "2026-04-11 12:30:45")
        self.assertEqual(record["summary"]["total_trades"], 8)
        self.assertEqual(record["ambiguous_entries"], 1)

    def test_build_builder_attempts_frame_orders_latest_first(self) -> None:
        attempts = [
            {
                "id": "builder-attempt-001",
                "attempt_number": 1,
                "created_at": "2026-04-11 12:00:00",
                "label": "RSI",
                "summary": {
                    "total_trades": 4,
                    "net_profit": 10.0,
                    "profit_factor": 1.2,
                    "max_drawdown": -2.0,
                    "win_rate": 50.0,
                },
                "ambiguous_entries": 0,
            },
            {
                "id": "builder-attempt-002",
                "attempt_number": 2,
                "created_at": "2026-04-11 12:10:00",
                "label": "Maxima da vela",
                "summary": {
                    "total_trades": 6,
                    "net_profit": 18.0,
                    "profit_factor": 1.4,
                    "max_drawdown": -3.0,
                    "win_rate": 66.7,
                },
                "ambiguous_entries": 2,
            },
        ]

        frame = build_builder_attempts_frame(attempts)

        self.assertEqual(list(frame["Tentativa"]), [2, 1])
        self.assertEqual(frame.iloc[0]["Configuracao"], "Maxima da vela")

    def test_resolve_previous_attempt_returns_prior_record(self) -> None:
        attempts = [
            {"id": "builder-attempt-001", "attempt_number": 1},
            {"id": "builder-attempt-002", "attempt_number": 2},
            {"id": "builder-attempt-003", "attempt_number": 3},
        ]

        previous_attempt = resolve_previous_attempt(attempts, "builder-attempt-003")

        self.assertEqual(previous_attempt, {"id": "builder-attempt-002", "attempt_number": 2})


if __name__ == "__main__":
    unittest.main()
