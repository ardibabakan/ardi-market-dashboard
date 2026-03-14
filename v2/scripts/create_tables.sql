-- ============================================================
-- ARDI MARKET COMMAND CENTER — DATABASE SCHEMA
-- Run this in Supabase SQL Editor
-- ============================================================

-- Portfolio positions (empty until real trades begin)
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    company TEXT,
    sector TEXT,
    entry_price DECIMAL,
    shares INTEGER,
    entry_date DATE,
    stop_loss DECIMAL,
    profit_target DECIMAL,
    status TEXT DEFAULT 'planned',  -- planned, open, closed
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Live price snapshots
CREATE TABLE IF NOT EXISTS price_snapshots (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    price DECIMAL,
    prev_close DECIMAL,
    change_pct DECIMAL,
    volume BIGINT,
    high_52w DECIMAL,
    low_52w DECIMAL,
    market_cap BIGINT,
    source TEXT DEFAULT 'yahoo',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_price_ticker_time ON price_snapshots(ticker, created_at DESC);

-- Crypto price snapshots
CREATE TABLE IF NOT EXISTS crypto_snapshots (
    id BIGSERIAL PRIMARY KEY,
    coin_id TEXT NOT NULL,
    symbol TEXT,
    price DECIMAL,
    change_24h_pct DECIMAL,
    change_7d_pct DECIMAL,
    market_cap BIGINT,
    volume_24h BIGINT,
    baseline DECIMAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crypto_time ON crypto_snapshots(created_at DESC);

-- Market indices and benchmarks
CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    name TEXT,
    value DECIMAL,
    change_pct DECIMAL,
    data_type TEXT,  -- index, commodity, currency, treasury
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_market_symbol_time ON market_data(symbol, created_at DESC);

-- Technical analysis results
CREATE TABLE IF NOT EXISTS technical_analysis (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    rsi DECIMAL,
    rsi_signal TEXT,
    macd DECIMAL,
    macd_signal_line DECIMAL,
    macd_histogram DECIMAL,
    macd_crossover TEXT,
    ma50 DECIMAL,
    ma200 DECIMAL,
    ma_status TEXT,  -- golden_cross, death_cross, bullish, bearish
    bb_upper DECIMAL,
    bb_lower DECIMAL,
    bb_position TEXT,
    volume_ratio DECIMAL,
    overall_score TEXT,  -- STRONG, BULLISH, NEUTRAL, BEARISH, WEAK
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ta_ticker_time ON technical_analysis(ticker, created_at DESC);

-- Signals (ceasefire, danger, stop loss, etc.)
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    signal_type TEXT NOT NULL,  -- ceasefire, danger, stop_loss, profit_target, thesis_invalidation, black_swan, opportunity
    signal_name TEXT NOT NULL,
    status TEXT NOT NULL,  -- fired, not_fired, unconfirmed
    confidence DECIMAL,
    details TEXT,
    source TEXT,
    second_source TEXT,  -- for two-source confirmation
    action_required TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_signals_type_time ON signals(signal_type, created_at DESC);

-- Daily reports
CREATE TABLE IF NOT EXISTS daily_reports (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL UNIQUE,
    action_today TEXT,
    portfolio_value DECIMAL,
    portfolio_change_pct DECIMAL,
    spy_change_pct DECIMAL,
    outperformance_pct DECIMAL,
    ceasefire_count INTEGER DEFAULT 0,
    danger_count INTEGER DEFAULT 0,
    conflict_day INTEGER,
    oil_price DECIMAL,
    oil_premium DECIMAL,
    vix DECIMAL,
    report_markdown TEXT,
    broad_universe_markdown TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fallen angels
CREATE TABLE IF NOT EXISTS fallen_angels (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    company TEXT,
    sector TEXT,
    current_price DECIMAL,
    high_52w DECIMAL,
    drop_pct DECIMAL,
    reason TEXT,
    recovery_trigger TEXT,
    quality_score TEXT,  -- strong, watch, avoid
    earnings_revisions TEXT,  -- up, down, flat
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fa_time ON fallen_angels(created_at DESC);

-- Macro data (FRED series, regime indicators)
CREATE TABLE IF NOT EXISTS macro_data (
    id BIGSERIAL PRIMARY KEY,
    series_id TEXT NOT NULL,
    series_name TEXT,
    value DECIMAL,
    previous_value DECIMAL,
    change_direction TEXT,  -- up, down, flat
    significance TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_macro_time ON macro_data(series_id, created_at DESC);

-- Market regime classification
CREATE TABLE IF NOT EXISTS regime (
    id BIGSERIAL PRIMARY KEY,
    regime_type TEXT NOT NULL,  -- risk_on_growth, risk_off_contraction, inflationary_shock, deflationary_shock
    confidence DECIMAL,
    supporting_evidence TEXT,
    implications TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Correlation matrix snapshots
CREATE TABLE IF NOT EXISTS correlations (
    id BIGSERIAL PRIMARY KEY,
    ticker_a TEXT NOT NULL,
    ticker_b TEXT NOT NULL,
    correlation_30d DECIMAL,
    correlation_90d DECIMAL,
    change_from_normal DECIMAL,
    alert TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- News and event detection
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT,  -- geopolitical, economic, corporate, natural_disaster, regulatory, technology
    headline TEXT,
    summary TEXT,
    source TEXT,
    second_source TEXT,
    affected_tickers TEXT,  -- comma-separated
    impact_assessment TEXT,
    severity TEXT,  -- minor, moderate, major, critical
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at DESC);

-- Geopolitical scenario probabilities
CREATE TABLE IF NOT EXISTS scenarios (
    id BIGSERIAL PRIMARY KEY,
    scenario_id TEXT NOT NULL,  -- iran_a, iran_b, iran_c, iran_d, ukraine_a, etc.
    scenario_name TEXT,
    probability DECIMAL,
    previous_probability DECIMAL,
    change_reason TEXT,
    market_impact TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- System health log
CREATE TABLE IF NOT EXISTS system_health (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,
    status TEXT NOT NULL,  -- ok, warning, error
    message TEXT,
    duration_seconds DECIMAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_health_time ON system_health(created_at DESC);

-- Agent run log
CREATE TABLE IF NOT EXISTS agent_runs (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT,  -- groups agents from the same orchestrator run
    agent_name TEXT NOT NULL,
    layer INTEGER,
    status TEXT NOT NULL,  -- started, completed, failed
    records_written INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_runs_time ON agent_runs(created_at DESC);

-- V1 historical data import
CREATE TABLE IF NOT EXISTS v1_historical (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT,  -- agent_0 through agent_9
    data JSONB,
    imported_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (but allow all for service role)
-- In production you'd add policies; for now, keep it open via anon key
