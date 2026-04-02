create table if not exists mining_campaigns (
    id text primary key,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    name text not null,
    evaluation_mode text not null,
    symbol text null,
    timeframe text null,
    dataset_id text not null,
    seed integer null,
    quantity integer not null default 0,
    status text not null default 'pending',
    configuration jsonb not null default '{}'::jsonb
);

alter table if exists backtest_metrics
    add column if not exists stability double precision not null default 0;

create index if not exists idx_mining_campaigns_created_at on mining_campaigns(created_at desc);
create index if not exists idx_backtest_runs_campaign_id on backtest_runs(campaign_id);
create index if not exists idx_backtest_runs_campaign_window on backtest_runs(campaign_id, window_index, dataset_role);
