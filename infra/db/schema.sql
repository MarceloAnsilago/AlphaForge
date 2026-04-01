create table if not exists strategies (
    id uuid primary key,
    name text not null,
    direction text not null,
    symbol text null,
    timeframe text null,
    origin text not null default 'manual',
    is_top_strategy boolean not null default false,
    best_score double precision null,
    best_backtest_run_id uuid null,
    latest_version_number integer not null default 0,
    current_version_id uuid null,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists strategy_versions (
    id uuid primary key,
    strategy_id uuid not null references strategies(id),
    version_number integer not null,
    spec_version text not null,
    strategy_name text not null,
    direction text not null,
    symbol text null,
    timeframe text null,
    strategy_fingerprint text not null,
    spec jsonb not null,
    created_at timestamptz not null default timezone('utc', now()),
    unique (strategy_id, version_number),
    unique (strategy_id, strategy_fingerprint)
);

create table if not exists backtest_runs (
    id uuid primary key,
    strategy_version_id uuid not null references strategy_versions(id),
    strategy_id uuid not null references strategies(id),
    symbol text null,
    timeframe text null,
    period_start timestamptz null,
    period_end timestamptz null,
    candle_count integer not null default 0,
    execution_parameters jsonb not null default '{}'::jsonb,
    input_fingerprint text not null,
    candle_fingerprint text null,
    strategy_fingerprint text not null,
    status text not null default 'completed',
    passed_filters boolean null,
    score double precision null,
    top_rank integer null,
    rejection_reason text null,
    is_top_strategy boolean not null default false,
    created_at timestamptz not null default timezone('utc', now())
);

create table if not exists backtest_metrics (
    id uuid primary key,
    backtest_run_id uuid not null unique references backtest_runs(id),
    total_trades integer not null default 0,
    winning_trades integer not null default 0,
    losing_trades integer not null default 0,
    win_rate double precision not null default 0,
    gross_profit double precision not null default 0,
    gross_loss double precision not null default 0,
    net_profit double precision not null default 0,
    average_pnl double precision not null default 0,
    average_holding_bars double precision not null default 0,
    max_drawdown double precision not null default 0,
    summary jsonb not null,
    created_at timestamptz not null default timezone('utc', now())
);

create table if not exists backtest_trades (
    id uuid primary key,
    backtest_run_id uuid not null references backtest_runs(id),
    trade_number integer not null,
    side text not null,
    entry_time timestamptz null,
    exit_time timestamptz null,
    entry_price double precision not null,
    exit_price double precision not null,
    pnl double precision not null default 0,
    holding_bars integer not null default 0,
    trade_payload jsonb not null,
    created_at timestamptz not null default timezone('utc', now()),
    unique (backtest_run_id, trade_number)
);
