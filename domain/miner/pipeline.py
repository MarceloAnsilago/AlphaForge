from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from domain.miner.fingerprint import backtest_input_fingerprint, strategy_spec_fingerprint
from domain.miner.scoring import (
    ScoreBreakdown,
    score_backtest_result,
    score_train_test_results,
    score_walk_forward_results,
)
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
class EvaluationWindow:
    window_index: int
    label: str
    partition_origin: str
    train_slice: DatasetSlice | None = None
    test_slice: DatasetSlice | None = None
    full_slice: DatasetSlice | None = None


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
    window_backtest_run_ids: list[str] = field(default_factory=list)


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
        windows = self._build_evaluation_windows(ordered_candles)

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

        if not windows:
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

        existing_version = self.strategy_repository.find_any_version_by_fingerprint(fingerprint)
        if existing_version is not None:
            duplicate_result = self._duplicate_result_if_all_runs_exist(
                strategy_spec=strategy_spec,
                strategy_version=existing_version,
                windows=windows,
            )
            if duplicate_result is not None:
                return duplicate_result
            strategy_row = self.strategy_repository.get_strategy(existing_version["strategy_id"])
            if strategy_row is None:
                raise ValueError(f"Strategy nao encontrada para versao persistida: {existing_version['strategy_id']}")
            strategy_version = existing_version
        else:
            created = self.strategy_service.create_strategy(strategy_spec, origin="miner")
            strategy_row = created["strategy"]
            strategy_version = created["strategy_version"]

        if self.evaluation.mode == "simple":
            return self._process_simple_candidate(
                strategy_spec=strategy_spec,
                strategy_row=strategy_row,
                strategy_version=strategy_version,
                fingerprint=fingerprint,
                window=windows[0],
            )

        if self.evaluation.mode == "robust":
            return self._process_robust_candidate(
                strategy_spec=strategy_spec,
                strategy_row=strategy_row,
                strategy_version=strategy_version,
                fingerprint=fingerprint,
                window=windows[0],
            )

        if self.evaluation.mode == "robust_walk_forward":
            return self._process_walk_forward_candidate(
                strategy_spec=strategy_spec,
                strategy_row=strategy_row,
                strategy_version=strategy_version,
                fingerprint=fingerprint,
                windows=windows,
            )

        raise ValueError(f"Modo de avaliacao nao suportado: {self.evaluation.mode}")

    def _duplicate_result_if_all_runs_exist(
        self,
        *,
        strategy_spec: StrategySpec,
        strategy_version: dict[str, Any],
        windows: list[EvaluationWindow],
    ) -> MinerPipelineResult | None:
        runs: list[dict[str, Any]] = []
        for data_slice in self._all_slices_for_windows(windows):
            input_fingerprint = backtest_input_fingerprint(
                strategy_version_id=strategy_version["id"],
                strategy_spec=strategy_spec,
                candles=data_slice.candles,
                execution_parameters=data_slice.execution_parameters,
            )
            run = self.backtest_repository.find_run_by_input_fingerprint(input_fingerprint)
            if run is None:
                return None
            runs.append(run)

        representative_run = self._representative_run(runs)
        train_runs = [run["id"] for run in runs if run.get("execution_parameters", {}).get("dataset_role") == "train"]
        test_runs = [run["id"] for run in runs if run.get("execution_parameters", {}).get("dataset_role") == "test"]

        return MinerPipelineResult(
            status="duplicate_persisted",
            strategy_fingerprint=strategy_version["strategy_fingerprint"],
            input_fingerprint=representative_run.get("input_fingerprint") if representative_run else None,
            strategy_id=strategy_version["strategy_id"],
            strategy_version_id=strategy_version["id"],
            backtest_run_id=representative_run.get("id") if representative_run else None,
            score=representative_run.get("score") if representative_run else None,
            passed_filters=bool(representative_run.get("passed_filters")) if representative_run else False,
            rejection_reason="existing_strategy_fingerprint",
            strategy_spec=strategy_spec,
            evaluation_mode=self.evaluation.mode,
            train_backtest_run_id=train_runs[0] if train_runs else None,
            test_backtest_run_id=test_runs[-1] if test_runs else None,
            window_backtest_run_ids=[run["id"] for run in runs],
        )

    def _process_simple_candidate(
        self,
        *,
        strategy_spec: StrategySpec,
        strategy_row: dict[str, Any],
        strategy_version: dict[str, Any],
        fingerprint: str,
        window: EvaluationWindow,
    ) -> MinerPipelineResult:
        if window.full_slice is None:
            raise ValueError("Janela simple sem full_slice.")

        execution = self._run_slice(
            strategy_version=strategy_version,
            strategy_spec=strategy_spec,
            data_slice=window.full_slice,
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
            window_backtest_run_ids=[run_row["id"]],
        )

    def _process_robust_candidate(
        self,
        *,
        strategy_spec: StrategySpec,
        strategy_row: dict[str, Any],
        strategy_version: dict[str, Any],
        fingerprint: str,
        window: EvaluationWindow,
    ) -> MinerPipelineResult:
        if window.train_slice is None or window.test_slice is None:
            raise ValueError("Janela robust sem slices de treino e teste.")

        train_execution = self._run_slice(
            strategy_version=strategy_version,
            strategy_spec=strategy_spec,
            data_slice=window.train_slice,
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
                window_backtest_run_ids=[train_run["id"]],
            )

        test_execution = self._run_slice(
            strategy_version=strategy_version,
            strategy_spec=strategy_spec,
            data_slice=window.test_slice,
        )
        final_score = score_train_test_results(train_execution["result"], test_execution["result"], self.filters, mode="robust")
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
            window_backtest_run_ids=[train_run["id"], test_run["id"]],
        )

    def _process_walk_forward_candidate(
        self,
        *,
        strategy_spec: StrategySpec,
        strategy_row: dict[str, Any],
        strategy_version: dict[str, Any],
        fingerprint: str,
        windows: list[EvaluationWindow],
    ) -> MinerPipelineResult:
        window_pairs: list[tuple[dict[str, Any], dict[str, Any], str]] = []
        window_run_ids: list[str] = []
        train_run_ids: list[str] = []
        test_run_ids: list[str] = []
        last_test_run: dict[str, Any] | None = None

        for window in windows:
            if window.train_slice is None or window.test_slice is None:
                raise ValueError("Janela walk-forward sem slices de treino e teste.")

            train_execution = self._run_slice(
                strategy_version=strategy_version,
                strategy_spec=strategy_spec,
                data_slice=window.train_slice,
            )
            train_score = score_backtest_result(train_execution["result"], self.filters)
            train_run = self._update_run_status(
                train_execution["persistence"]["backtest_run"]["id"],
                score=train_score.score,
                passed_filters=train_score.passed_filters,
                rejection_reason=train_score.rejection_reason,
                status="window_train_validated" if train_score.passed_filters else "window_train_filtered",
            ) or train_execution["persistence"]["backtest_run"]

            test_execution = self._run_slice(
                strategy_version=strategy_version,
                strategy_spec=strategy_spec,
                data_slice=window.test_slice,
            )
            window_score = score_train_test_results(
                train_execution["result"],
                test_execution["result"],
                self.filters,
                mode="robust_walk_forward",
            )
            test_run = self._update_run_status(
                test_execution["persistence"]["backtest_run"]["id"],
                score=window_score.score,
                passed_filters=window_score.passed_filters,
                rejection_reason=window_score.rejection_reason,
                status="window_accepted" if window_score.passed_filters else "window_filtered",
            ) or test_execution["persistence"]["backtest_run"]

            window_pairs.append((train_execution["result"], test_execution["result"], window.label))
            train_run_ids.append(train_run["id"])
            test_run_ids.append(test_run["id"])
            window_run_ids.extend([train_run["id"], test_run["id"]])
            last_test_run = test_run

        final_score = score_walk_forward_results(
            window_pairs,
            self.filters,
            minimum_window_pass_rate=self.evaluation.minimum_window_pass_rate,
        )
        if last_test_run is None:
            raise ValueError("Walk-forward sem run de teste final.")

        aggregate_run = self._update_run_status(
            last_test_run["id"],
            score=final_score.score,
            passed_filters=final_score.passed_filters,
            rejection_reason=final_score.rejection_reason,
            status="accepted" if final_score.passed_filters else "filtered",
            execution_parameters={
                **dict(last_test_run.get("execution_parameters") or {}),
                "window_result": {
                    "score": last_test_run.get("score"),
                    "passed_filters": last_test_run.get("passed_filters"),
                    "rejection_reason": last_test_run.get("rejection_reason"),
                    "status": last_test_run.get("status"),
                },
                "aggregate_result": {
                    "score": final_score.score,
                    "passed_filters": final_score.passed_filters,
                    "rejection_reason": final_score.rejection_reason,
                    "status": "accepted" if final_score.passed_filters else "filtered",
                },
            },
        ) or last_test_run

        return MinerPipelineResult(
            status="accepted" if final_score.passed_filters else "filtered",
            strategy_fingerprint=fingerprint,
            input_fingerprint=aggregate_run["input_fingerprint"],
            strategy_id=strategy_row["id"],
            strategy_version_id=strategy_version["id"],
            backtest_run_id=aggregate_run["id"],
            score=final_score.score,
            passed_filters=final_score.passed_filters,
            rejection_reason=final_score.rejection_reason,
            persisted=True,
            strategy_spec=strategy_spec,
            score_breakdown=final_score,
            evaluation_mode="robust_walk_forward",
            train_backtest_run_id=train_run_ids[0] if train_run_ids else None,
            test_backtest_run_id=test_run_ids[-1] if test_run_ids else None,
            window_backtest_run_ids=window_run_ids,
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
        execution_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        values: dict[str, Any] = {
            "score": score,
            "passed_filters": passed_filters,
            "rejection_reason": rejection_reason,
            "status": status,
        }
        if execution_parameters is not None:
            values["execution_parameters"] = execution_parameters
        return self.backtest_repository.update_backtest_run(
            backtest_run_id,
            values,
        )

    def _build_evaluation_windows(self, candles: pd.DataFrame) -> list[EvaluationWindow]:
        if self.evaluation.mode == "simple":
            return [
                EvaluationWindow(
                    window_index=0,
                    label="window_0",
                    partition_origin="full",
                    full_slice=self._make_slice(
                        role="full",
                        candles=candles,
                        start_index=0,
                        end_index=max(len(candles) - 1, 0),
                        window_index=0,
                        window_label="window_0",
                        window_count=1,
                        partition_origin="full",
                    ),
                )
            ]

        if self.evaluation.mode == "robust":
            window = self._build_single_split_window(candles)
            return [window] if window is not None else []

        if self.evaluation.mode == "robust_walk_forward":
            return self._build_walk_forward_windows(candles)

        raise ValueError(f"Modo de avaliacao nao suportado: {self.evaluation.mode}")

    def _build_single_split_window(self, candles: pd.DataFrame) -> EvaluationWindow | None:
        total_candles = len(candles)
        if total_candles == 0:
            return None

        split_index = int(total_candles * self.evaluation.train_ratio)
        split_index = max(split_index, self.evaluation.minimum_partition_size)
        split_index = min(split_index, total_candles - self.evaluation.minimum_partition_size)

        if split_index <= 0 or split_index >= total_candles:
            return None

        train = candles.iloc[:split_index].reset_index(drop=True).copy()
        test = candles.iloc[split_index:].reset_index(drop=True).copy()
        if len(train) < self.evaluation.minimum_partition_size or len(test) < self.evaluation.minimum_partition_size:
            return None

        return EvaluationWindow(
            window_index=0,
            label="window_0",
            partition_origin="single_split",
            train_slice=self._make_slice(
                role="train",
                candles=train,
                start_index=0,
                end_index=split_index - 1,
                window_index=0,
                window_label="window_0",
                window_count=1,
                partition_origin="single_split",
            ),
            test_slice=self._make_slice(
                role="test",
                candles=test,
                start_index=split_index,
                end_index=total_candles - 1,
                window_index=0,
                window_label="window_0",
                window_count=1,
                partition_origin="single_split",
            ),
        )

    def _build_walk_forward_windows(self, candles: pd.DataFrame) -> list[EvaluationWindow]:
        configured_windows = self.evaluation.walk_forward_windows
        if configured_windows:
            return self._build_configured_walk_forward_windows(candles, configured_windows)
        return self._build_automatic_walk_forward_windows(candles)

    def _build_configured_walk_forward_windows(
        self,
        candles: pd.DataFrame,
        configured_windows: list[dict[str, Any]],
    ) -> list[EvaluationWindow]:
        windows: list[EvaluationWindow] = []
        window_count = len(configured_windows)

        for window_index, window_config in enumerate(configured_windows):
            train_start = int(window_config["train_start"])
            train_end = int(window_config["train_end"])
            test_start = int(window_config["test_start"])
            test_end = int(window_config["test_end"])
            label = str(window_config.get("label", f"window_{window_index}"))

            if train_start < 0 or test_start <= train_end or test_end >= len(candles):
                return []
            if (train_end - train_start + 1) < self.evaluation.minimum_partition_size:
                return []
            if (test_end - test_start + 1) < self.evaluation.minimum_partition_size:
                return []

            train = candles.iloc[train_start : train_end + 1].reset_index(drop=True).copy()
            test = candles.iloc[test_start : test_end + 1].reset_index(drop=True).copy()
            windows.append(
                EvaluationWindow(
                    window_index=window_index,
                    label=label,
                    partition_origin="configured_walk_forward",
                    train_slice=self._make_slice(
                        role="train",
                        candles=train,
                        start_index=train_start,
                        end_index=train_end,
                        window_index=window_index,
                        window_label=label,
                        window_count=window_count,
                        partition_origin="configured_walk_forward",
                    ),
                    test_slice=self._make_slice(
                        role="test",
                        candles=test,
                        start_index=test_start,
                        end_index=test_end,
                        window_index=window_index,
                        window_label=label,
                        window_count=window_count,
                        partition_origin="configured_walk_forward",
                    ),
                )
            )

        return windows

    def _build_automatic_walk_forward_windows(self, candles: pd.DataFrame) -> list[EvaluationWindow]:
        total_candles = len(candles)
        if total_candles == 0:
            return []

        train_size = max(int(total_candles * self.evaluation.train_ratio), self.evaluation.minimum_partition_size)
        test_size = max(int(total_candles * self.evaluation.test_ratio), self.evaluation.minimum_partition_size)
        step_size = (
            max(int(total_candles * self.evaluation.walk_forward_step_ratio), 1)
            if self.evaluation.walk_forward_step_ratio is not None
            else test_size
        )

        if train_size + test_size > total_candles:
            return []

        ranges: list[tuple[int, int, int, int]] = []
        if self.evaluation.expanding_train:
            train_end = train_size - 1
            while True:
                test_start = train_end + 1
                test_end = test_start + test_size - 1
                if test_end >= total_candles:
                    break
                ranges.append((0, train_end, test_start, test_end))
                if self.evaluation.max_walk_forward_windows and len(ranges) >= self.evaluation.max_walk_forward_windows:
                    break
                train_end += step_size
        else:
            train_start = 0
            while True:
                train_end = train_start + train_size - 1
                test_start = train_end + 1
                test_end = test_start + test_size - 1
                if test_end >= total_candles:
                    break
                ranges.append((train_start, train_end, test_start, test_end))
                if self.evaluation.max_walk_forward_windows and len(ranges) >= self.evaluation.max_walk_forward_windows:
                    break
                train_start += step_size

        windows: list[EvaluationWindow] = []
        window_count = len(ranges)
        for window_index, (train_start, train_end, test_start, test_end) in enumerate(ranges):
            label = f"window_{window_index}"
            train = candles.iloc[train_start : train_end + 1].reset_index(drop=True).copy()
            test = candles.iloc[test_start : test_end + 1].reset_index(drop=True).copy()
            windows.append(
                EvaluationWindow(
                    window_index=window_index,
                    label=label,
                    partition_origin="auto_walk_forward",
                    train_slice=self._make_slice(
                        role="train",
                        candles=train,
                        start_index=train_start,
                        end_index=train_end,
                        window_index=window_index,
                        window_label=label,
                        window_count=window_count,
                        partition_origin="auto_walk_forward",
                    ),
                    test_slice=self._make_slice(
                        role="test",
                        candles=test,
                        start_index=test_start,
                        end_index=test_end,
                        window_index=window_index,
                        window_label=label,
                        window_count=window_count,
                        partition_origin="auto_walk_forward",
                    ),
                )
            )

        return windows

    def _make_slice(
        self,
        *,
        role: str,
        candles: pd.DataFrame,
        start_index: int,
        end_index: int,
        window_index: int,
        window_label: str,
        window_count: int,
        partition_origin: str,
    ) -> DatasetSlice:
        return DatasetSlice(
            role=role,
            dataset_id=self.evaluation.dataset_id,
            candles=candles,
            start_index=start_index,
            end_index=end_index,
            execution_parameters=self._build_execution_parameters(
                role=role,
                start_index=start_index,
                end_index=end_index,
                candle_count=len(candles),
                window_index=window_index,
                window_label=window_label,
                window_count=window_count,
                partition_origin=partition_origin,
            ),
        )

    def _all_slices_for_windows(self, windows: list[EvaluationWindow]) -> list[DatasetSlice]:
        slices: list[DatasetSlice] = []
        for window in windows:
            if window.full_slice is not None:
                slices.append(window.full_slice)
            if window.train_slice is not None:
                slices.append(window.train_slice)
            if window.test_slice is not None:
                slices.append(window.test_slice)
        return slices

    def _representative_run(self, runs: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not runs:
            return None
        test_runs = [run for run in runs if run.get("execution_parameters", {}).get("dataset_role") == "test"]
        if test_runs:
            return sorted(
                test_runs,
                key=lambda item: (
                    int(item.get("execution_parameters", {}).get("window_index", 0)),
                    str(item.get("created_at", "")),
                ),
            )[-1]
        return sorted(runs, key=lambda item: str(item.get("created_at", "")))[-1]

    def _build_execution_parameters(
        self,
        *,
        role: str,
        start_index: int,
        end_index: int,
        candle_count: int,
        window_index: int,
        window_label: str,
        window_count: int,
        partition_origin: str,
    ) -> dict[str, Any]:
        execution_parameters = dict(self.execution_parameters)
        execution_parameters.setdefault("fill_policy", "next_candle_open")
        execution_parameters.setdefault("campaign_id", f"{self.evaluation.dataset_id}:{self.evaluation.mode}")
        execution_parameters.setdefault("strategy_origin", "miner")
        execution_parameters.update(
            {
                "evaluation_mode": self.evaluation.mode,
                "dataset_role": role,
                "split_method": "walk_forward" if self.evaluation.mode == "robust_walk_forward" else self.evaluation.split_method,
                "dataset_id": self.evaluation.dataset_id,
                "window_index": window_index,
                "window_label": window_label,
                "window_count": window_count,
                "partition_origin": partition_origin,
                "window_range": {
                    "start_index": start_index,
                    "end_index": end_index,
                    "candle_count": candle_count,
                },
                "additional_datasets": self.evaluation.additional_datasets,
                "walk_forward_windows": self.evaluation.walk_forward_windows,
                "expanding_train": self.evaluation.expanding_train,
            }
        )
        if self.evaluation.mode in {"robust", "robust_walk_forward"}:
            execution_parameters["train_ratio"] = self.evaluation.train_ratio
            execution_parameters["minimum_partition_size"] = self.evaluation.minimum_partition_size
        if self.evaluation.mode == "robust_walk_forward":
            execution_parameters["test_ratio"] = self.evaluation.test_ratio
            execution_parameters["walk_forward_step_ratio"] = self.evaluation.walk_forward_step_ratio
            execution_parameters["minimum_window_pass_rate"] = self.evaluation.minimum_window_pass_rate
            execution_parameters["max_walk_forward_windows"] = self.evaluation.max_walk_forward_windows
        return execution_parameters
