from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from domain.miner.fingerprint import backtest_input_fingerprint, strategy_spec_fingerprint
from domain.miner.scoring import ScoreBreakdown, score_backtest_result
from domain.miner.space import MinerFilterConfig
from domain.strategy.normalizer import normalize_strategy
from domain.strategy.spec import StrategyDraft, StrategySpec
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.backtest_service import BacktestService
from services.strategy_service import StrategyService


@dataclass(slots=True)
class MinerPipelineResult:
    status: str
    strategy_fingerprint: str
    input_fingerprint: str | None
    strategy_id: str | None
    strategy_version_id: str | None
    backtest_run_id: str | None
    score: float | None
    passed_filters: bool
    rejection_reason: str | None = None
    persisted: bool = False
    strategy_spec: StrategySpec | None = None
    score_breakdown: ScoreBreakdown | None = None


@dataclass(slots=True)
class MinerPipeline:
    strategy_service: StrategyService
    backtest_service: BacktestService
    strategy_repository: StrategyRepository
    backtest_repository: BacktestRepository
    filters: MinerFilterConfig
    execution_parameters: dict[str, Any] = field(default_factory=dict)
    seen_fingerprints: set[str] = field(default_factory=set)

    def process_candidate(self, candidate: dict[str, Any] | StrategyDraft | StrategySpec, candles: pd.DataFrame) -> MinerPipelineResult:
        strategy_spec = normalize_strategy(candidate)
        fingerprint = strategy_spec_fingerprint(strategy_spec)

        if fingerprint in self.seen_fingerprints:
            return MinerPipelineResult(
                status="duplicate_in_batch",
                strategy_fingerprint=fingerprint,
                input_fingerprint=None,
                strategy_id=None,
                strategy_version_id=None,
                backtest_run_id=None,
                score=None,
                passed_filters=False,
                rejection_reason="duplicate_strategy_fingerprint",
                strategy_spec=strategy_spec,
            )
        self.seen_fingerprints.add(fingerprint)

        existing_version = self.strategy_repository.find_any_version_by_fingerprint(fingerprint)
        if existing_version is not None:
            existing_input_fingerprint = backtest_input_fingerprint(
                strategy_version_id=existing_version["id"],
                strategy_spec=strategy_spec,
                candles=candles,
                execution_parameters=self.execution_parameters,
            )
            existing_run = self.backtest_repository.find_run_by_input_fingerprint(existing_input_fingerprint)
            return MinerPipelineResult(
                status="duplicate_persisted",
                strategy_fingerprint=fingerprint,
                input_fingerprint=existing_input_fingerprint,
                strategy_id=existing_version["strategy_id"],
                strategy_version_id=existing_version["id"],
                backtest_run_id=existing_run["id"] if existing_run else None,
                score=existing_run.get("score") if existing_run else None,
                passed_filters=bool(existing_run.get("passed_filters")) if existing_run else False,
                rejection_reason="existing_strategy_fingerprint",
                strategy_spec=strategy_spec,
            )

        created = self.strategy_service.create_strategy(strategy_spec, origin="miner")
        strategy_row = created["strategy"]
        strategy_version = created["strategy_version"]

        execution = self.backtest_service.run_and_persist_backtest(
            strategy_version=strategy_version,
            strategy=strategy_spec,
            candles=candles,
            execution_parameters=self.execution_parameters,
        )
        score_breakdown = score_backtest_result(execution["result"], self.filters)
        run_row = self.backtest_repository.update_backtest_run(
            execution["persistence"]["backtest_run"]["id"],
            {
                "score": score_breakdown.score,
                "passed_filters": score_breakdown.passed_filters,
                "rejection_reason": score_breakdown.rejection_reason,
                "status": "scored" if score_breakdown.passed_filters else "filtered",
            },
        ) or execution["persistence"]["backtest_run"]

        return MinerPipelineResult(
            status="accepted" if score_breakdown.passed_filters else "filtered",
            strategy_fingerprint=fingerprint,
            input_fingerprint=run_row["input_fingerprint"],
            strategy_id=strategy_row["id"],
            strategy_version_id=strategy_version["id"],
            backtest_run_id=run_row["id"],
            score=score_breakdown.score,
            passed_filters=score_breakdown.passed_filters,
            rejection_reason=score_breakdown.rejection_reason,
            persisted=True,
            strategy_spec=strategy_spec,
            score_breakdown=score_breakdown,
        )
