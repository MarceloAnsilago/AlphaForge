from __future__ import annotations

import argparse
import json

import pandas as pd

from infra.db.supabase_client import InMemoryDatabaseClient, build_supabase_client_from_env
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.backtest_service import BacktestService
from services.miner_service import MinerService
from services.strategy_service import StrategyService
from domain.miner.space import MinerEvaluationConfig


def _load_candles(csv_path: str) -> pd.DataFrame:
    candles = pd.read_csv(csv_path)
    if "time" not in candles.columns:
        raise ValueError("CSV precisa ter a coluna 'time'.")
    candles["time"] = pd.to_datetime(candles["time"], utc=False)
    return candles


def _build_db_client(backend: str):
    if backend == "supabase":
        return build_supabase_client_from_env()
    return InMemoryDatabaseClient()


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa lote local do minerador do AlphaForge.")
    parser.add_argument("--dataset", required=True, help="Caminho CSV com candles.")
    parser.add_argument("--quantity", type=int, default=100, help="Quantidade de estrategias candidatas.")
    parser.add_argument("--seed", type=int, default=42, help="Seed do random search.")
    parser.add_argument("--symbol", default=None, help="Simbolo associado ao dataset.")
    parser.add_argument("--timeframe", default=None, help="Timeframe associado ao dataset.")
    parser.add_argument("--top-k", type=int, default=5, help="Quantidade de top estrategias marcadas.")
    parser.add_argument("--max-rules", type=int, default=2, help="Numero maximo de regras por estrategia.")
    parser.add_argument("--db", choices=["memory", "supabase"], default="memory", help="Backend de persistencia.")
    parser.add_argument("--mode", choices=["simple", "robust"], default="simple", help="Modo de avaliacao do minerador.")
    parser.add_argument("--train-ratio", type=float, default=0.7, help="Percentual do dataset usado no treino no modo robusto.")
    parser.add_argument("--min-split-bars", type=int, default=20, help="Numero minimo de candles por particao no modo robusto.")
    args = parser.parse_args()

    candles = _load_candles(args.dataset)
    db = _build_db_client(args.db)
    strategy_repository = StrategyRepository(db)
    backtest_repository = BacktestRepository(db)
    strategy_service = StrategyService(strategy_repository)
    backtest_service = BacktestService(backtest_repository)
    miner_service = MinerService(
        strategy_service=strategy_service,
        backtest_service=backtest_service,
        strategy_repository=strategy_repository,
        backtest_repository=backtest_repository,
    )

    result = miner_service.mine_batch(
        candles=candles,
        quantity=args.quantity,
        symbol=args.symbol,
        timeframe=args.timeframe,
        seed=args.seed,
        top_k=args.top_k,
        max_rules_per_strategy=args.max_rules,
        evaluation=MinerEvaluationConfig(
            mode=args.mode,
            train_ratio=args.train_ratio,
            minimum_partition_size=args.min_split_bars,
        ),
    )
    print(json.dumps(result["summary"], ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
