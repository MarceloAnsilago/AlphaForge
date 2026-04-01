from __future__ import annotations

from typing import Any

from infra.db.supabase_client import DatabaseClient, utc_now_iso

import uuid


class StrategyRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self._db = db

    def create_strategy(
        self,
        *,
        name: str,
        direction: str,
        symbol: str | None,
        timeframe: str | None,
    ) -> dict[str, Any]:
        return self._db.insert(
            "strategies",
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "direction": direction,
                "symbol": symbol,
                "timeframe": timeframe,
                "latest_version_number": 0,
                "current_version_id": None,
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            },
        )

    def get_strategy(self, strategy_id: str) -> dict[str, Any] | None:
        rows = self._db.select("strategies", filters={"id": strategy_id}, limit=1)
        return rows[0] if rows else None

    def create_strategy_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._db.insert("strategy_versions", payload)

    def list_strategy_versions(self, strategy_id: str) -> list[dict[str, Any]]:
        return self._db.select(
            "strategy_versions",
            filters={"strategy_id": strategy_id},
            order_by="version_number",
            ascending=True,
        )

    def get_strategy_version(self, strategy_version_id: str) -> dict[str, Any] | None:
        rows = self._db.select("strategy_versions", filters={"id": strategy_version_id}, limit=1)
        return rows[0] if rows else None

    def find_version_by_fingerprint(self, strategy_id: str, strategy_fingerprint: str) -> dict[str, Any] | None:
        rows = self._db.select(
            "strategy_versions",
            filters={"strategy_id": strategy_id, "strategy_fingerprint": strategy_fingerprint},
            limit=1,
        )
        return rows[0] if rows else None

    def set_current_version(self, strategy_id: str, strategy_version_id: str, latest_version_number: int) -> dict[str, Any] | None:
        rows = self._db.update(
            "strategies",
            filters={"id": strategy_id},
            values={
                "current_version_id": strategy_version_id,
                "latest_version_number": latest_version_number,
                "updated_at": utc_now_iso(),
            },
        )
        return rows[0] if rows else None
