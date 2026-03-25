CREATE TABLE IF NOT EXISTS stock_strategy_runs (
    id SERIAL PRIMARY KEY,
    strategy_code VARCHAR(64) NOT NULL,
    strategy_name VARCHAR(128) NOT NULL,
    as_of DATE NOT NULL,
    label_horizon INTEGER NOT NULL DEFAULT 60,
    status VARCHAR(32) NOT NULL DEFAULT 'ready',
    model_path TEXT,
    train_rows INTEGER NOT NULL DEFAULT 0,
    scored_rows INTEGER NOT NULL DEFAULT 0,
    evaluation_json TEXT NOT NULL DEFAULT '{}',
    leaderboard_json TEXT NOT NULL DEFAULT '[]',
    feature_importance_json TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stock_strategy_scores (
    run_id INTEGER NOT NULL REFERENCES stock_strategy_runs(id) ON DELETE CASCADE,
    symbol VARCHAR(32) NOT NULL,
    as_of DATE NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    rank INTEGER NOT NULL,
    percentile DOUBLE PRECISION NOT NULL,
    expected_return DOUBLE PRECISION,
    signal VARCHAR(32) NOT NULL DEFAULT 'watch',
    summary TEXT,
    feature_values_json TEXT NOT NULL DEFAULT '{}',
    driver_factors_json TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_stock_strategy_runs_code_updated
ON stock_strategy_runs(strategy_code, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_stock_strategy_scores_symbol_asof
ON stock_strategy_scores(symbol, as_of DESC);

CREATE INDEX IF NOT EXISTS idx_stock_strategy_scores_run_rank
ON stock_strategy_scores(run_id, rank);
