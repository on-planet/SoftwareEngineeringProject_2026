CREATE TABLE IF NOT EXISTS auth_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(512) NOT NULL,
    password_salt VARCHAR(128) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_verification_codes (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    purpose VARCHAR(32) NOT NULL,
    code_hash VARCHAR(128) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_watch_targets (
    user_id INTEGER NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS user_bought_targets (
    user_id INTEGER NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    buy_price DOUBLE PRECISION NOT NULL,
    lots DOUBLE PRECISION NOT NULL,
    buy_date DATE NOT NULL,
    fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    note VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS user_alert_rules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(128) NOT NULL,
    rule_type VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    price_operator VARCHAR(8),
    threshold DOUBLE PRECISION,
    event_type VARCHAR(64),
    research_kind VARCHAR(32),
    lookback_days INTEGER NOT NULL DEFAULT 7,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    note VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_stock_pools (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(128) NOT NULL,
    market VARCHAR(16) NOT NULL DEFAULT 'A',
    symbols_json TEXT NOT NULL DEFAULT '[]',
    note VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_saved_stock_filters (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(128) NOT NULL,
    market VARCHAR(16) NOT NULL DEFAULT 'A',
    keyword VARCHAR(128) NOT NULL DEFAULT '',
    sector VARCHAR(128) NOT NULL DEFAULT '',
    sort VARCHAR(8) NOT NULL DEFAULT 'asc',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_users_email ON auth_users(email);
CREATE INDEX IF NOT EXISTS idx_email_verification_codes_email ON email_verification_codes(email);
CREATE INDEX IF NOT EXISTS idx_email_verification_codes_purpose ON email_verification_codes(purpose);
CREATE INDEX IF NOT EXISTS idx_email_verification_codes_expires_at ON email_verification_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_watch_targets_user ON user_watch_targets(user_id);
CREATE INDEX IF NOT EXISTS idx_user_bought_targets_user ON user_bought_targets(user_id);
CREATE INDEX IF NOT EXISTS idx_user_alert_rules_user ON user_alert_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_user_alert_rules_symbol ON user_alert_rules(symbol);
CREATE INDEX IF NOT EXISTS idx_user_alert_rules_type ON user_alert_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_user_stock_pools_user ON user_stock_pools(user_id);
CREATE INDEX IF NOT EXISTS idx_user_saved_stock_filters_user ON user_saved_stock_filters(user_id);
