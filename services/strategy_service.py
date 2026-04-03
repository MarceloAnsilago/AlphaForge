from __future__ import annotations

from typing import Any

import uuid

from domain.miner.fingerprint import strategy_spec_fingerprint
from domain.strategy.normalizer import normalize_strategy
from domain.strategy.spec import StrategyDraft, StrategySpec
from infra.db.supabase_client import utc_now_iso
from infra.repositories.strategy_repository import StrategyRepository

class StrategyService:
    def __init__(self, strategy_repository: StrategyRepository) -> None:
        self._strategy_repository = strategy_repository

    def ensure_strategy(
        self,
        strategy: dict[str, Any] | StrategyDraft | StrategySpec,
        origin: str = "manual",
    ) -> dict[str, Any]:
        strategy_spec = normalize_strategy(strategy)
        fingerprint = strategy_spec_fingerprint(strategy_spec)
        existing_version = self._strategy_repository.find_any_version_by_fingerprint(fingerprint)
        if existing_version is not None:
            strategy_row = self._strategy_repository.get_strategy(existing_version["strategy_id"])
            if strategy_row is None:
                raise ValueError(f"Strategy nao encontrada: {existing_version['strategy_id']}")
            return {
                "strategy": strategy_row,
                "strategy_version": existing_version,
                "strategy_spec": strategy_spec,
                "deduplicated": True,
            }
        created = self.create_strategy(strategy_spec, origin=origin)
        return {
            **created,
            "deduplicated": False,
        }

    def create_strategy(self, strategy: dict[str, Any] | StrategyDraft | StrategySpec, origin: str = "manual") -> dict[str, Any]:
        strategy_spec = normalize_strategy(strategy)
        strategy_row = self._strategy_repository.create_strategy(
            name=strategy_spec.name,
            direction=strategy_spec.direction,
            symbol=strategy_spec.market.get("symbol"),
            timeframe=strategy_spec.market.get("timeframe"),
            origin=origin,
        )
        version_row = self._create_strategy_version_row(strategy_row["id"], 1, strategy_spec)
        version = self._strategy_repository.create_strategy_version(version_row)
        self._strategy_repository.set_current_version(strategy_row["id"], version["id"], 1)
        strategy_state = self._strategy_repository.get_strategy(strategy_row["id"]) or strategy_row
        return {
            "strategy": strategy_state,
            "strategy_version": version,
            "strategy_spec": strategy_spec,
        }

    def create_strategy_version(self, strategy_id: str, strategy: dict[str, Any] | StrategyDraft | StrategySpec) -> dict[str, Any]:
        strategy_row = self._strategy_repository.get_strategy(strategy_id)
        if strategy_row is None:
            raise ValueError(f"Strategy nao encontrada: {strategy_id}")

        strategy_spec = normalize_strategy(strategy)
        fingerprint = strategy_spec_fingerprint(strategy_spec)
        existing = self._strategy_repository.find_version_by_fingerprint(strategy_id, fingerprint)
        if existing is not None:
            return {
                "strategy": strategy_row,
                "strategy_version": existing,
                "strategy_spec": strategy_spec,
                "deduplicated": True,
            }

        version_number = int(strategy_row.get("latest_version_number", 0)) + 1
        version_row = self._create_strategy_version_row(strategy_id, version_number, strategy_spec)
        version = self._strategy_repository.create_strategy_version(version_row)
        strategy_state = self._strategy_repository.set_current_version(strategy_id, version["id"], version_number) or strategy_row
        return {
            "strategy": strategy_state,
            "strategy_version": version,
            "strategy_spec": strategy_spec,
            "deduplicated": False,
        }

    def _create_strategy_version_row(self, strategy_id: str, version_number: int, strategy_spec: StrategySpec) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "strategy_id": strategy_id,
            "version_number": version_number,
            "spec_version": strategy_spec.version,
            "strategy_name": strategy_spec.name,
            "direction": strategy_spec.direction,
            "symbol": strategy_spec.market.get("symbol"),
            "timeframe": strategy_spec.market.get("timeframe"),
            "strategy_fingerprint": strategy_spec_fingerprint(strategy_spec),
            "spec": strategy_spec.to_dict(),
            "created_at": utc_now_iso(),
        }
