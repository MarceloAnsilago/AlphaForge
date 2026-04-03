from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from infra.db.supabase_client import DatabaseClient, build_database_client
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.mining_campaign_repository import MiningCampaignRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.backtest_service import BacktestService
from services.miner_service import MinerService
from services.mining_campaign_service import MiningCampaignService
from services.strategy_service import StrategyService


@dataclass(slots=True)
class WebBackendContext:
    db: DatabaseClient
    backend_mode: str
    backend_status: str
    strategy_repository: StrategyRepository
    backtest_repository: BacktestRepository
    mining_campaign_repository: MiningCampaignRepository
    strategy_service: StrategyService
    backtest_service: BacktestService
    miner_service: MinerService
    mining_campaign_service: MiningCampaignService


@lru_cache(maxsize=1)
def get_web_backend_context() -> WebBackendContext:
    configured_backend = os.getenv("ALPHAFORGE_DB_BACKEND", "").strip() or "auto"
    db, backend_mode, backend_status = build_database_client(configured_backend)

    strategy_repository = StrategyRepository(db)
    backtest_repository = BacktestRepository(db)
    mining_campaign_repository = MiningCampaignRepository(db)
    strategy_service = StrategyService(strategy_repository)
    backtest_service = BacktestService(backtest_repository)
    mining_campaign_service = MiningCampaignService(
        mining_campaign_repository=mining_campaign_repository,
        backtest_repository=backtest_repository,
    )
    miner_service = MinerService(
        strategy_service=strategy_service,
        backtest_service=backtest_service,
        strategy_repository=strategy_repository,
        backtest_repository=backtest_repository,
        mining_campaign_service=mining_campaign_service,
    )
    return WebBackendContext(
        db=db,
        backend_mode=backend_mode,
        backend_status=backend_status,
        strategy_repository=strategy_repository,
        backtest_repository=backtest_repository,
        mining_campaign_repository=mining_campaign_repository,
        strategy_service=strategy_service,
        backtest_service=backtest_service,
        miner_service=miner_service,
        mining_campaign_service=mining_campaign_service,
    )
