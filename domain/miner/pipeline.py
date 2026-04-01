from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from domain.miner.fingerprint import strategy_spec_fingerprint
from domain.miner.scoring import ScoreBreakdown, score_backtest_result, score_train_test_results
from domain.miner.space import MinerEvaluationConfig, MinerFilterConfig
from domain.strategy.normalizer import normalize_strategy
from domain.strategy.spec import StrategyDraft, StrategySpec
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.backtest_service import BacktestService
from services.strategy_service import StrategyService


@dataclass(slots=True)
class DatasetSlice:
    role: str
    dataset_id: str
    candles: pd.DataFrame
    start_index: int
    end_index: int
    execution_parameters: dict[str, Any]


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
    evaluation_mode: str = "simple"
    train_backtest_run_id: str | None = None
    test_backtest_run_id: str | None = None


@dataclass(slots=True)
class MinerPipeline:
    strategy_service: StrategyService
    backtest_service: BacktestService
    strategy_repository: StrategyRepository
    backtest_repository: BacktestRepository
    filters: MinerFilterConfig
    execution_parameters: dict[str, Any] = field(default_factory=dict)
    evaluation: MinerEvaluationConfig = field(default_factory=MinerEvaluationConfig)
    seen_fingerprints: set[str] = field(default_factory=set)

    def process_candidate(self, candidate: dict[str, Any] | StrategyDraft | StrategySpec, candles: pd.DataFrame) -> MinerPipelineResult:
        ordered_candles = candles.sort_values("time").reset_index(drop=True).copy()
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
                evaluation_mode=self.evaluation.mode,
            )
        self.seen_fingerprints.add(fingerprint)

        existing_version = self.strategy_repository.find_any_version_by_fingerprint(fingerprint)
        if existing_version is not None:
            existing_runs = self.backtest_repository.list_backtest_runs(existing_version["id"])
            representative_run = existing_runs[0] if existing_runs else None
            return MinerPipelineResult(
                status="duplicate_persisted",
                strategy_fingerprint=fingerprint,
                input_fingerprint=representative_run.get("input_fingerprint") if representative_run else None,
                strategy_id=existing_version["strategy_id"],
                strategy_version_id=existing_version["id"],
                backtest_run_id=representative_run.get("id") if representative_run else None,
                score=representative_run.get("score") if representative_run else None,
                passed_filters=bool(representative_run.get("passed_filters")) if representative_run else False,
                rejection_reason="existing_strategy_fingerprint",
                strategy_spec=strategy_spec,
                evaluation_mode=self.evaluation.mode,
            )

        slices = self._build_dataset_slices(ordered_candles)
        if not slices:
            return MinerPipelineResult(
                status="filtered",
                strategy_fingerprint=fingerprint,
                input_fingerprint=None,
                strategy_id=None,
                strategy_version_id=None,
                backtest_run_id=None,
                score=None,
                passed_filters=False,
                rejection_reason="insufficient_split_data",
                strategy_spec=strategy_spec,
                evaluation_mode=self.evaluation.mode,
            )

        created = self.strategy_service.create_strategy(strategy_spec, origin="miner")
        strategy_row = created["strategy"]
        strategy_version = created["strategy_version"]

        if self.evaluation.mode == "robust":
            return self._process_robust_candidate(
                strategy_spec=strategy_spec,
                strategy_row=strategy_row,
                strategy_version=strategy_version,
                fingerprint=fingerprint,
                slices=slices,
            )

        return self._process_simple_candidate(
            strategy_spec=strategy_spec,
            strategy_row=strategy_row,
            strategy_version=strategy_version,
            fingerprint=fingerprint,
            data_slice=slices[0],
        )

    def _process_simple_candidate(
        self,
        *,
        strategy_spec: StrategySpec,
        strategy_row: dict[str, Any],
        strategy_version: dict[str, Any],
        fingerprint: str,
        data_slice: DatasetSlice,
    ) -> MinerPipelineResult:
        execution = self._run_slice(
            strategy_version=strategy_version,
            strategy_spec=strategy_spec,
            data_slice=data_slice,
        )
        score_breakdown = score_backtest_result(execution["result"], self.filters)
        run_row = self._update_run_status(
            execution["persistence"]["backtest_run"]["id"],
            score=score_breakdown.score,
            passed_filters=score_breakdown.passed_filters,
            rejection_reason=score_breakdown.rejection_reason,
            status="accepted" if score_breakdown.passed_filters else "filtered",
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
            evaluation_mode="simple",
        )

    def _process_robust_candidate(
        self,
        *,
        strategy_spec: StrategySpec,
        strategy_row: dict[str, Any],
        strategy_version: dict[str, Any],
        fingerprint: str,
        slices: list[DatasetSlice],
    ) -> MinerPipelineResult:
        train_slice = next(data_slice for data_slice in slices if data_slice.role == "train")
        test_slice = next(data_slice for data_slice in slices if data_slice.role == "test")

        train_execution = self._run_slice(
            strategy_version=strategy_version,
            strategy_spec=strategy_spec,
            data_slice=train_slice,
        )
        train_score = score_backtest_result(train_execution["result"], self.filters)
        train_run = self._update_run_status(
            train_execution["persistence"]["backtest_run"]["id"],
            score=train_score.score,
            passed_filters=train_score.passed_filters,
            rejection_reason=train_score.rejection_reason,
            status="validated_train" if train_score.passed_filters else "train_filtered",
        ) or train_execution["persistence"]["backtest_run"]

        if not train_score.passed_filters:
            return MinerPipelineResult(
                status="filtered",
                strategy_fingerprint=fingerprint,
                input_fingerprint=train_run["input_fingerprint"],
                strategy_id=strategy_row["id"],
                strategy_version_id=strategy_version["id"],
                backtest_run_id=train_run["id"],
                score=train_score.score,
                passed_filters=False,
                rejection_reason=train_score.rejection_reason,
                persisted=True,
                strategy_spec=strategy_spec,
                score_breakdown=train_score,
                evaluation_mode="robust",
                train_backtest_run_id=train_run["id"],
            )

        test_execution = self._run_slice(
            strategy_version=strategy_version,
            strategy_spec=strategy_spec,
            data_slice=test_slice,
        )
        final_score = score_train_test_results(train_execution["result"], test_execution["result"], self.filters)
        test_run = self._update_run_status(
            test_execution["persistence"]["backtest_run"]["id"],
            score=final_score.score,
            passed_filters=final_score.passed_filters,
            rejection_reason=final_score.rejection_reason,
            status="accepted" if final_score.passed_filters else "filtered",
        ) or test_execution["persistence"]["backtest_run"]

        return MinerPipelineResult(
            status="accepted" if final_score.passed_filters else "filtered",
            strategy_fingerprint=fingerprint,
            input_fingerprint=test_run["input_fingerprint"],
            strategy_id=strategy_row["id"],
            strategy_version_id=strategy_version["id"],
            backtest_run_id=test_run["id"],
            score=final_score.score,
            passed_filters=final_score.passed_filters,
            rejection_reason=final_score.rejection_reason,
            persisted=True,
            strategy_spec=strategy_spec,
            score_breakdown=final_score,
            evaluation_mode="robust",
            train_backtest_run_id=train_run["id"],
            test_backtest_run_id=test_run["id"],
        )

    def _run_slice(
        self,
        *,
        strategy_version: dict[str, Any],
        strategy_spec: StrategySpec,
        data_slice: DatasetSlice,
    ) -> dict[str, Any]:
        return self.backtest_service.run_and_persist_backtest(
            strategy_version=strategy_version,
            strategy=strategy_spec,
            candles=data_slice.candles,
            execution_parameters=data_slice.execution_parameters,
        )

    def _update_run_status(
        self,
        backtest_run_id: str,
        *,
        score: float | None,
        passed_filters: bool | None,
        rejection_reason: str | None,
        status: str,
    ) -> dict[str, Any] | None:
        return self.backtest_repository.update_backtest_run(
            backtest_run_id,
            {
                "score": score,
                "passed_filters": passed_filters,
                "rejection_reason": rejection_reason,
                "status": status,
            },
        )

    def _build_dataset_slices(self, candles: pd.DataFrame) -> list[DatasetSlice]:
        if self.evaluation.mode == "simple":
            return [
                DatasetSlice(
                    role="full",
                    dataset_id=self.evaluation.dataset_id,
                    candles=candles.copy(),
                    start_index=0,
                    end_index=max(len(candles) - 1, 0),
                    execution_parameters=self._build_execution_parameters(
                        role="full",
                        start_index=0,
                        end_index=max(len(candles) - 1, 0),
                        candle_count=len(candles),
                    ),
                )
            ]

        if self.evaluation.mode != "robust":
            raise ValueError(f"Modo de avaliacao nao suportado: {self.evaluation.mode}")
        if self.evaluation.split_method != "single_split":
            raise ValueError(f"Split nao suportado nesta fase: {self.evaluation.split_method}")

        total_candles = len(candles)
        if total_candles == 0:
            return []

        split_index = int(total_candles * self.evaluation.train_ratio)
        split_index = max(split_index, self.evaluation.minimum_partition_size)
        split_index = min(split_index, total_candles - self.evaluation.minimum_partition_size)

        if split_index <= 0 or split_index >= total_candles:
            return []

        train = candles.iloc[:split_index].reset_index(drop=True).copy()
        test = candles.iloc[split_index:].reset_index(drop=True).copy()
        if len(train) < self.evaluation.minimum_partition_size or len(test) < self.evaluation.minimum_partition_size:
            return []

        return [
            DatasetSlice(
                role="train",
                dataset_id=self.evaluation.dataset_id,
                candles=train,
                start_index=0,
                end_index=split_index - 1,
                execution_parameters=self._build_execution_parameters(
                    role="train",
                    start_index=0,
                    end_index=split_index - 1,
                    candle_count=len(train),
                ),
            ),
            DatasetSlice(
                role="test",
                dataset_id=self.evaluation.dataset_id,
                candles=test,
                start_index=split_index,
                end_index=total_candles - 1,
                execution_parameters=self._build_execution_parameters(
                    role="test",
                    start_index=split_index,
                    end_index=total_candles - 1,
                    candle_count=len(test),
                ),
            ),
        ]

    def _build_execution_parameters(
        self,
        *,
        role: str,
        start_index: int,
        end_index: int,
        candle_count: int,
    ) -> dict[str, Any]:
        execution_parameters = dict(self.execution_parameters)
        execution_parameters.setdefault("fill_policy", "next_candle_open")
        execution_parameters.update(
            {
                "evaluation_mode": self.evaluation.mode,
                "dataset_role": role,
                "split_method": self.evaluation.split_method,
                "dataset_id": self.evaluation.dataset_id,
                "window_index": 0,
                "window_range": {
                    "start_index": start_index,
                    "end_index": end_index,
                    "candle_count": candle_count,
                },
                "additional_datasets": self.evaluation.additional_datasets,
                "walk_forward_windows": self.evaluation.walk_forward_windows,
            }
        )
        if self.evaluation.mode == "robust":
            execution_parameters["train_ratio"] = self.evaluation.train_ratio
            execution_parameters["minimum_partition_size"] = self.evaluation.minimum_partition_size
        return execution_parameters
