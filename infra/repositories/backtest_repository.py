from __future__ import annotations

from statistics import mean
from typing import Any

from infra.db.supabase_client import DatabaseClient


class BacktestRepository:
    _FINAL_RUN_STATUSES = {"accepted", "filtered", "top"}

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

    def list_backtest_runs(self, strategy_version_id: str) -> list[dict[str, Any]]:
        return self._db.select(
            "backtest_runs",
            filters={"strategy_version_id": strategy_version_id},
            order_by="created_at",
            ascending=False,
        )

    def find_run_by_input_fingerprint(self, input_fingerprint: str) -> dict[str, Any] | None:
        rows = self._db.select("backtest_runs", filters={"input_fingerprint": input_fingerprint}, limit=1)
        return rows[0] if rows else None

    def get_backtest_metrics(self, backtest_run_id: str) -> dict[str, Any] | None:
        rows = self._db.select("backtest_metrics", filters={"backtest_run_id": backtest_run_id}, limit=1)
        return rows[0] if rows else None

    def list_backtest_trades(self, backtest_run_id: str) -> list[dict[str, Any]]:
        return self._db.select(
            "backtest_trades",
            filters={"backtest_run_id": backtest_run_id},
            order_by="trade_number",
            ascending=True,
        )

    def update_backtest_run(self, backtest_run_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        rows = self._db.update(
            "backtest_runs",
            filters={"id": backtest_run_id},
            values=values,
        )
        return rows[0] if rows else None

    def list_runs_by_campaign(self, campaign_id: str, *, final_only: bool = False) -> list[dict[str, Any]]:
        rows = self._db.select(
            "backtest_runs",
            filters={"campaign_id": campaign_id},
            order_by="created_at",
            ascending=False,
        )
        if final_only:
            rows = [row for row in rows if str(row.get("status", "")) in self._FINAL_RUN_STATUSES]
        return rows

    def list_top_strategies_by_campaign(self, campaign_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        runs = [
            row
            for row in self.list_runs_by_campaign(campaign_id, final_only=True)
            if row.get("score") is not None and bool(row.get("passed_filters"))
        ]
        runs = sorted(
            runs,
            key=lambda item: (
                -(float(item.get("score") or 0.0)),
                int(item.get("top_rank") or 10_000),
                str(item.get("created_at") or ""),
            ),
        )

        strategies = {row["id"]: row for row in self._db.select("strategies")}
        versions = {row["id"]: row for row in self._db.select("strategy_versions")}
        metrics_by_run = self.get_metrics_map([row["id"] for row in runs])

        ranked: list[dict[str, Any]] = []
        seen_strategy_ids: set[str] = set()
        for run in runs:
            strategy_id = str(run.get("strategy_id"))
            if strategy_id in seen_strategy_ids:
                continue
            seen_strategy_ids.add(strategy_id)
            strategy = strategies.get(strategy_id, {})
            version = versions.get(str(run.get("strategy_version_id")), {})
            ranked.append(
                {
                    "campaign_id": campaign_id,
                    "strategy_id": strategy_id,
                    "strategy_name": strategy.get("name") or version.get("strategy_name"),
                    "strategy_direction": strategy.get("direction") or version.get("direction"),
                    "strategy_version_id": run.get("strategy_version_id"),
                    "version_number": version.get("version_number"),
                    "backtest_run_id": run.get("id"),
                    "score": run.get("score"),
                    "top_rank": run.get("top_rank"),
                    "is_top_strategy": bool(run.get("is_top_strategy")),
                    "evaluation_mode": run.get("evaluation_mode"),
                    "dataset_role": run.get("dataset_role"),
                    "window_index": run.get("window_index"),
                    "window_label": run.get("window_label"),
                    "status": run.get("status"),
                    "passed_filters": bool(run.get("passed_filters")),
                    "metrics": metrics_by_run.get(str(run.get("id"))),
                    "created_at": run.get("created_at"),
                }
            )
            if len(ranked) >= max(limit, 0):
                break

        return ranked

    def list_window_performance_by_campaign(self, campaign_id: str) -> list[dict[str, Any]]:
        runs = self.list_runs_by_campaign(campaign_id)
        metrics_by_run = self.get_metrics_map([row["id"] for row in runs])
        grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}

        for run in runs:
            key = (
                run.get("window_index"),
                run.get("window_label"),
                run.get("dataset_role"),
                run.get("partition_origin"),
                run.get("evaluation_mode"),
            )
            grouped.setdefault(key, []).append(run)

        aggregates: list[dict[str, Any]] = []
        for key, grouped_runs in grouped.items():
            window_index, window_label, dataset_role, partition_origin, evaluation_mode = key
            scores = [self._window_score(run) for run in grouped_runs if self._window_score(run) is not None]
            metrics = [metrics_by_run.get(str(run["id"])) for run in grouped_runs if metrics_by_run.get(str(run["id"])) is not None]
            approved_runs = sum(1 for run in grouped_runs if self._window_passed(run) is True)
            total_runs = len(grouped_runs)
            aggregates.append(
                {
                    "campaign_id": campaign_id,
                    "window_index": window_index,
                    "window_label": window_label,
                    "dataset_role": dataset_role,
                    "partition_origin": partition_origin,
                    "evaluation_mode": evaluation_mode,
                    "total_runs": total_runs,
                    "approved_runs": approved_runs,
                    "pass_rate": (approved_runs / total_runs) if total_runs else 0.0,
                    "average_score": mean(scores) if scores else 0.0,
                    "average_net_profit": mean(float(item.get("net_profit", 0.0)) for item in metrics) if metrics else 0.0,
                    "average_profit_factor": mean(float(item.get("profit_factor", 0.0)) for item in metrics) if metrics else 0.0,
                    "average_stability": mean(float(item.get("stability", 0.0)) for item in metrics) if metrics else 0.0,
                    "average_drawdown": mean(float(item.get("max_drawdown", 0.0)) for item in metrics) if metrics else 0.0,
                }
            )

        return sorted(
            aggregates,
            key=lambda item: (
                int(item.get("window_index") or 0),
                str(item.get("dataset_role") or ""),
                str(item.get("partition_origin") or ""),
            ),
        )

    def get_metrics_map(self, backtest_run_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not backtest_run_ids:
            return {}
        target_ids = {str(run_id) for run_id in backtest_run_ids}
        rows = self._db.select("backtest_metrics")
        return {
            str(row["backtest_run_id"]): row
            for row in rows
            if str(row.get("backtest_run_id")) in target_ids
        }

    def get_run_with_metrics(self, backtest_run_id: str) -> dict[str, Any] | None:
        run = self.get_backtest_run(backtest_run_id)
        if run is None:
            return None
        return {
            **run,
            "metrics": self.get_backtest_metrics(backtest_run_id),
        }

    def _window_score(self, run: dict[str, Any]) -> float | None:
        window_result = self._window_result(run)
        value = window_result.get("score")
        return float(value) if value is not None else None

    def _window_passed(self, run: dict[str, Any]) -> bool | None:
        window_result = self._window_result(run)
        value = window_result.get("passed_filters")
        return None if value is None else bool(value)

    def _window_result(self, run: dict[str, Any]) -> dict[str, Any]:
        execution_parameters = run.get("execution_parameters") or {}
        if (
            run.get("evaluation_mode") == "robust_walk_forward"
            and run.get("dataset_role") == "test"
            and isinstance(execution_parameters.get("window_result"), dict)
        ):
            return dict(execution_parameters["window_result"])
        return {
            "score": run.get("score"),
            "passed_filters": run.get("passed_filters"),
            "status": run.get("status"),
            "rejection_reason": run.get("rejection_reason"),
        }
