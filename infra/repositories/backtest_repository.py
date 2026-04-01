from __future__ import annotations

from typing import Any

from infra.db.supabase_client import DatabaseClient


class BacktestRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self._db = db

    def create_backtest_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._db.insert("backtest_runs", payload)

    def create_backtest_metrics(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._db.insert("backtest_metrics", payload)

    def create_backtest_trades(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._db.insert_many("backtest_trades", payloads)

    def get_backtest_run(self, backtest_run_id: str) -> dict[str, Any] | None:
        rows = self._db.select("backtest_runs", filters={"id": backtest_run_id}, limit=1)
        return rows[0] if rows else None

    def list_backtest_trades(self, backtest_run_id: str) -> list[dict[str, Any]]:
        return self._db.select(
            "backtest_trades",
            filters={"backtest_run_id": backtest_run_id},
            order_by="trade_number",
            ascending=True,
        )
