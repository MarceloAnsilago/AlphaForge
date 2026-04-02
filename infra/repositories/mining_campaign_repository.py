from __future__ import annotations

from typing import Any

import uuid

from infra.db.supabase_client import DatabaseClient, utc_now_iso


class MiningCampaignRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self._db = db

    def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": payload.get("id") or str(uuid.uuid4()),
            "created_at": payload.get("created_at") or utc_now_iso(),
            "updated_at": payload.get("updated_at") or utc_now_iso(),
            "name": payload["name"],
            "evaluation_mode": payload["evaluation_mode"],
            "symbol": payload.get("symbol"),
            "timeframe": payload.get("timeframe"),
            "dataset_id": payload["dataset_id"],
            "seed": payload.get("seed"),
            "quantity": int(payload.get("quantity", 0)),
            "status": payload.get("status", "pending"),
            "configuration": dict(payload.get("configuration") or {}),
        }
        return self._db.insert("mining_campaigns", row)

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        rows = self._db.select("mining_campaigns", filters={"id": campaign_id}, limit=1)
        return rows[0] if rows else None

    def list_campaigns(self) -> list[dict[str, Any]]:
        return self._db.select(
            "mining_campaigns",
            order_by="created_at",
            ascending=False,
        )

    def update_campaign(self, campaign_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        rows = self._db.update(
            "mining_campaigns",
            filters={"id": campaign_id},
            values={
                **values,
                "updated_at": utc_now_iso(),
            },
        )
        return rows[0] if rows else None
