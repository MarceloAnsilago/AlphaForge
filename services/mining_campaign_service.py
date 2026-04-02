from __future__ import annotations

from dataclasses import asdict, is_dataclass
from statistics import mean
from typing import Any

from domain.miner.space import MinerEvaluationConfig, MinerSearchSpace
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.mining_campaign_repository import MiningCampaignRepository


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _json_ready(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


class MiningCampaignService:
    def __init__(
        self,
        *,
        mining_campaign_repository: MiningCampaignRepository,
        backtest_repository: BacktestRepository,
    ) -> None:
        self._mining_campaign_repository = mining_campaign_repository
        self._backtest_repository = backtest_repository

    def ensure_campaign(
        self,
        *,
        campaign_id: str | None,
        name: str | None,
        evaluation: MinerEvaluationConfig,
        search_space: MinerSearchSpace,
        quantity: int,
        seed: int | None,
        execution_parameters: dict[str, Any] | None = None,
        status: str = "running",
    ) -> dict[str, Any]:
        existing = self._mining_campaign_repository.get_campaign(campaign_id) if campaign_id else None
        if existing is not None:
            configuration = dict(existing.get("configuration") or {})
            configuration["execution_parameters"] = _json_ready(execution_parameters or {})
            configuration["evaluation"] = _json_ready(evaluation)
            configuration["filters"] = _json_ready(search_space.filters)
            configuration["search_space"] = _json_ready(search_space)
            return self._mining_campaign_repository.update_campaign(
                existing["id"],
                {
                    "name": name or existing.get("name"),
                    "status": status,
                    "quantity": quantity,
                    "seed": seed,
                    "configuration": configuration,
                },
            ) or existing

        symbol = search_space.market.get("symbol")
        timeframe = search_space.market.get("timeframe")
        campaign_name = name or self._default_campaign_name(
            evaluation_mode=evaluation.mode,
            symbol=symbol,
            timeframe=timeframe,
            dataset_id=evaluation.dataset_id,
        )
        return self._mining_campaign_repository.create_campaign(
            {
                "id": campaign_id,
                "name": campaign_name,
                "evaluation_mode": evaluation.mode,
                "symbol": symbol,
                "timeframe": timeframe,
                "dataset_id": evaluation.dataset_id,
                "seed": seed,
                "quantity": quantity,
                "status": status,
                "configuration": {
                    "evaluation": _json_ready(evaluation),
                    "filters": _json_ready(search_space.filters),
                    "search_space": _json_ready(search_space),
                    "execution_parameters": _json_ready(execution_parameters or {}),
                },
            }
        )

    def complete_campaign(
        self,
        campaign_id: str,
        *,
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        campaign = self._mining_campaign_repository.get_campaign(campaign_id)
        if campaign is None:
            return None

        configuration = dict(campaign.get("configuration") or {})
        configuration["batch_summary"] = _json_ready(result.get("summary", {}))
        configuration["search_space"] = _json_ready(result.get("search_space", configuration.get("search_space", {})))
        return self._mining_campaign_repository.update_campaign(
            campaign_id,
            {
                "status": "completed",
                "configuration": configuration,
            },
        )

    def fail_campaign(self, campaign_id: str, *, error_message: str) -> dict[str, Any] | None:
        campaign = self._mining_campaign_repository.get_campaign(campaign_id)
        if campaign is None:
            return None

        configuration = dict(campaign.get("configuration") or {})
        configuration["error"] = {"message": error_message}
        return self._mining_campaign_repository.update_campaign(
            campaign_id,
            {
                "status": "failed",
                "configuration": configuration,
            },
        )

    def list_campaigns(self) -> list[dict[str, Any]]:
        return self._mining_campaign_repository.list_campaigns()

    def list_campaign_runs(self, campaign_id: str) -> list[dict[str, Any]]:
        runs = self._backtest_repository.list_runs_by_campaign(campaign_id)
        metrics_by_run = self._backtest_repository.get_metrics_map([row["id"] for row in runs])
        return [{**row, "metrics": metrics_by_run.get(str(row["id"]))} for row in runs]

    def list_campaign_top_strategies(self, campaign_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        return self._backtest_repository.list_top_strategies_by_campaign(campaign_id, limit=limit)

    def list_campaign_window_performance(self, campaign_id: str) -> list[dict[str, Any]]:
        return self._backtest_repository.list_window_performance_by_campaign(campaign_id)

    def get_campaign_summary(self, campaign_id: str) -> dict[str, Any] | None:
        campaign = self._mining_campaign_repository.get_campaign(campaign_id)
        if campaign is None:
            return None

        runs = self.list_campaign_runs(campaign_id)
        final_runs = [row for row in runs if str(row.get("status", "")) in {"accepted", "filtered", "top"}]
        strategy_stats = self._build_strategy_stats(runs, final_runs)
        top_strategies = self.list_campaign_top_strategies(campaign_id, limit=5)
        batch_summary = dict((campaign.get("configuration") or {}).get("batch_summary") or {})

        return {
            "campaign_id": campaign_id,
            "requested_quantity": int(campaign.get("quantity") or 0),
            "generated_quantity": int(batch_summary.get("processed", campaign.get("quantity") or 0)),
            "deduplicated_quantity": int(batch_summary.get("duplicates", 0)),
            "approved_quantity": int(batch_summary.get("accepted", sum(1 for item in strategy_stats if item["approved"]))),
            "top_scores": [float(item.get("score") or 0.0) for item in top_strategies if item.get("score") is not None],
            "average_pass_rate": mean(item["pass_rate"] for item in strategy_stats) if strategy_stats else 0.0,
            "average_stability": mean(item["stability"] for item in strategy_stats) if strategy_stats else 0.0,
            "final_run_count": len(final_runs),
            "strategy_count": len(strategy_stats),
        }

    def get_campaign_audit(self, campaign_id: str, *, top_limit: int = 10) -> dict[str, Any] | None:
        campaign = self._mining_campaign_repository.get_campaign(campaign_id)
        if campaign is None:
            return None

        return {
            "campaign": campaign,
            "summary": self.get_campaign_summary(campaign_id),
            "top_strategies": self.list_campaign_top_strategies(campaign_id, limit=top_limit),
            "runs": self.list_campaign_runs(campaign_id),
            "window_performance": self.list_campaign_window_performance(campaign_id),
        }

    def _build_strategy_stats(
        self,
        runs: list[dict[str, Any]],
        final_runs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        final_by_strategy = {
            str(row.get("strategy_id")): row
            for row in final_runs
            if row.get("strategy_id") is not None
        }
        grouped_test_runs: dict[str, list[dict[str, Any]]] = {}
        for row in runs:
            if row.get("strategy_id") is None or row.get("dataset_role") != "test":
                continue
            grouped_test_runs.setdefault(str(row["strategy_id"]), []).append(row)

        stats: list[dict[str, Any]] = []
        for strategy_id, final_run in final_by_strategy.items():
            if str(final_run.get("evaluation_mode")) == "robust_walk_forward":
                ordered_test_runs = sorted(
                    grouped_test_runs.get(strategy_id, []),
                    key=lambda item: int(item.get("window_index") or 0),
                )
                window_results = [self._window_result(row) for row in ordered_test_runs]
                stabilities = [
                    float((row.get("metrics") or {}).get("stability", 0.0))
                    for row in ordered_test_runs
                    if row.get("metrics") is not None
                ]
                stats.append(
                    {
                        "strategy_id": strategy_id,
                        "approved": bool(final_run.get("passed_filters")),
                        "pass_rate": (
                            sum(1 for item in window_results if item.get("passed_filters") is True) / len(window_results)
                            if window_results
                            else 0.0
                        ),
                        "stability": mean(stabilities) if stabilities else 0.0,
                    }
                )
                continue

            metrics = final_run.get("metrics") or {}
            stats.append(
                {
                    "strategy_id": strategy_id,
                    "approved": bool(final_run.get("passed_filters")),
                    "pass_rate": 1.0 if bool(final_run.get("passed_filters")) else 0.0,
                    "stability": float(metrics.get("stability", 0.0)),
                }
            )

        return stats

    def _window_result(self, run: dict[str, Any]) -> dict[str, Any]:
        execution_parameters = run.get("execution_parameters") or {}
        if isinstance(execution_parameters.get("window_result"), dict):
            return dict(execution_parameters["window_result"])
        return {
            "score": run.get("score"),
            "passed_filters": run.get("passed_filters"),
            "status": run.get("status"),
            "rejection_reason": run.get("rejection_reason"),
        }

    def _default_campaign_name(
        self,
        *,
        evaluation_mode: str,
        symbol: str | None,
        timeframe: str | None,
        dataset_id: str,
    ) -> str:
        market = " ".join(item for item in [symbol, timeframe] if item)
        if market:
            return f"{evaluation_mode}:{dataset_id}:{market}"
        return f"{evaluation_mode}:{dataset_id}"
