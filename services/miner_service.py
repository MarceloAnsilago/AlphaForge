from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from domain.miner.generator import RandomStrategyGenerator
from domain.miner.pipeline import MinerPipeline, MinerPipelineResult
from domain.miner.space import MinerEvaluationConfig, MinerFilterConfig, MinerSearchSpace, default_search_space
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.backtest_service import BacktestService
from services.mining_campaign_service import MiningCampaignService
from services.strategy_service import StrategyService


@dataclass(slots=True)
class MinerBatchSummary:
    requested: int
    processed: int
    accepted: int
    filtered: int
    duplicates: int
    top_ranked: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MinerService:
    def __init__(
        self,
        *,
        strategy_service: StrategyService,
        backtest_service: BacktestService,
        strategy_repository: StrategyRepository,
        backtest_repository: BacktestRepository,
        mining_campaign_service: MiningCampaignService,
    ) -> None:
        self._strategy_service = strategy_service
        self._backtest_service = backtest_service
        self._strategy_repository = strategy_repository
        self._backtest_repository = backtest_repository
        self._mining_campaign_service = mining_campaign_service

    def mine_batch(
        self,
        *,
        candles: pd.DataFrame,
        quantity: int,
        symbol: str | None,
        timeframe: str | None,
        seed: int | None = None,
        top_k: int = 5,
        max_rules_per_strategy: int = 2,
        filters: MinerFilterConfig | None = None,
        evaluation: MinerEvaluationConfig | None = None,
        execution_parameters: dict[str, Any] | None = None,
        initial_volume: float = 1.0,
        fixed_spread: float = 0.0,
        campaign_id: str | None = None,
        campaign_name: str | None = None,
    ) -> dict[str, Any]:
        search_space = default_search_space(
            symbol=symbol,
            timeframe=timeframe,
            max_rules_per_strategy=max_rules_per_strategy,
            initial_volume=initial_volume,
            fixed_spread=fixed_spread,
            filters=filters,
            evaluation=evaluation,
        )
        return self.mine_batch_with_space(
            candles=candles,
            quantity=quantity,
            search_space=search_space,
            seed=seed,
            top_k=top_k,
            execution_parameters=execution_parameters,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
        )

    def mine_batch_with_space(
        self,
        *,
        candles: pd.DataFrame,
        quantity: int,
        search_space: MinerSearchSpace,
        seed: int | None = None,
        top_k: int = 5,
        execution_parameters: dict[str, Any] | None = None,
        campaign_id: str | None = None,
        campaign_name: str | None = None,
    ) -> dict[str, Any]:
        execution_parameters = dict(execution_parameters or {"fill_policy": "next_candle_open"})
        campaign = self._mining_campaign_service.ensure_campaign(
            campaign_id=campaign_id or execution_parameters.get("campaign_id"),
            name=campaign_name or execution_parameters.get("campaign_name"),
            evaluation=search_space.evaluation,
            search_space=search_space,
            quantity=quantity,
            seed=seed,
            execution_parameters=execution_parameters,
            status="running",
        )
        execution_parameters["campaign_id"] = campaign["id"]

        generator = RandomStrategyGenerator(search_space=search_space, seed=seed)
        pipeline = MinerPipeline(
            strategy_service=self._strategy_service,
            backtest_service=self._backtest_service,
            strategy_repository=self._strategy_repository,
            backtest_repository=self._backtest_repository,
            filters=search_space.filters,
            execution_parameters=execution_parameters,
            evaluation=search_space.evaluation,
        )

        try:
            results: list[MinerPipelineResult] = []
            for candidate_index in range(quantity):
                candidate = generator.generate(candidate_index + 1)
                results.append(pipeline.process_candidate(candidate, candles))

            top_candidates = [result for result in results if result.status == "accepted" and result.score is not None]
            top_candidates = sorted(top_candidates, key=lambda item: item.score or 0.0, reverse=True)

            for rank, result in enumerate(top_candidates[: max(top_k, 0)], start=1):
                if result.strategy_id is None or result.backtest_run_id is None:
                    continue
                self._strategy_repository.update_strategy(
                    result.strategy_id,
                    {
                        "is_top_strategy": True,
                        "best_score": result.score,
                        "best_backtest_run_id": result.backtest_run_id,
                    },
                )
                self._backtest_repository.update_backtest_run(
                    result.backtest_run_id,
                    {
                        "is_top_strategy": True,
                        "top_rank": rank,
                        "status": "top",
                        "score": result.score,
                        "passed_filters": True,
                    },
                )

            summary = MinerBatchSummary(
                requested=quantity,
                processed=len(results),
                accepted=sum(1 for result in results if result.status == "accepted"),
                filtered=sum(1 for result in results if result.status == "filtered"),
                duplicates=sum(1 for result in results if result.status.startswith("duplicate")),
                top_ranked=min(len(top_candidates), max(top_k, 0)),
            )

            response = {
                "campaign": campaign,
                "summary": summary.to_dict(),
                "results": [asdict(result) for result in results],
                "search_space": asdict(search_space),
            }
            self._mining_campaign_service.complete_campaign(campaign["id"], result=response)
            return response
        except Exception as exc:
            self._mining_campaign_service.fail_campaign(campaign["id"], error_message=str(exc))
            raise
