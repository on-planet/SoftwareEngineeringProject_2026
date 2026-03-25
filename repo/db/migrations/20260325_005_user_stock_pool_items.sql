CREATE TABLE IF NOT EXISTS user_stock_pool_items (
    pool_id INTEGER NOT NULL REFERENCES user_stock_pools(id) ON DELETE CASCADE,
    symbol VARCHAR(32) NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pool_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_user_stock_pool_items_symbol ON user_stock_pool_items(symbol);
CREATE INDEX IF NOT EXISTS idx_user_stock_pool_items_pool_position ON user_stock_pool_items(pool_id, position);

INSERT INTO user_stock_pool_items (pool_id, symbol, position)
SELECT DISTINCT ON (normalized.pool_id, normalized.symbol)
    normalized.pool_id,
    normalized.symbol,
    normalized.position
FROM (
    SELECT
        pool.id AS pool_id,
        UPPER(BTRIM(item.value)) AS symbol,
        item.ordinality - 1 AS position
    FROM user_stock_pools AS pool
    CROSS JOIN LATERAL jsonb_array_elements_text(
        COALESCE(NULLIF(BTRIM(pool.symbols_json), ''), '[]')::jsonb
    ) WITH ORDINALITY AS item(value, ordinality)
) AS normalized
WHERE normalized.symbol <> ''
ORDER BY normalized.pool_id, normalized.symbol, normalized.position
ON CONFLICT (pool_id, symbol) DO NOTHING;
