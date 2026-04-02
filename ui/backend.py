from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from infra.db.supabase_client import (
    DatabaseClient,
    InMemoryDatabaseClient,
    SupabaseClientError,
    build_supabase_client_from_env,
)
from infra.repositories.backtest_repository import BacktestRepository
from infra.repositories.mining_campaign_repository import MiningCampaignRepository
from infra.repositories.strategy_repository import StrategyRepository
from services.mining_campaign_service import MiningCampaignService


@dataclass(slots=True)
class UiBackendContext:
    db: DatabaseClient
    backend_mode: str
    backend_status: str
    strategy_repository: StrategyRepository
    backtest_repository: BacktestRepository
    mining_campaign_repository: MiningCampaignRepository
    mining_campaign_service: MiningCampaignService


@st.cache_resource(show_spinner=False)
def get_ui_backend_context() -> UiBackendContext:
    try:
        db = build_supabase_client_from_env()
        backend_mode = "supabase"
        backend_status = "Conectado ao backend persistente."
    except SupabaseClientError as exc:
        db = InMemoryDatabaseClient()
        backend_mode = "memory"
        backend_status = (
            "Backend persistente indisponivel. A interface de campanhas esta em modo memoria: "
            f"{exc}"
        )

    strategy_repository = StrategyRepository(db)
    backtest_repository = BacktestRepository(db)
    mining_campaign_repository = MiningCampaignRepository(db)
    mining_campaign_service = MiningCampaignService(
        mining_campaign_repository=mining_campaign_repository,
        backtest_repository=backtest_repository,
    )
    return UiBackendContext(
        db=db,
        backend_mode=backend_mode,
        backend_status=backend_status,
        strategy_repository=strategy_repository,
        backtest_repository=backtest_repository,
        mining_campaign_repository=mining_campaign_repository,
        mining_campaign_service=mining_campaign_service,
    )
