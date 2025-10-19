-- 市场加密货币列表数据表
-- 用于存储市场加密货币列表数据

CREATE TABLE IF NOT EXISTS market_crypto_listings (
    id SERIAL PRIMARY KEY,
    crypto_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    slug VARCHAR(255),
    cmc_rank INTEGER,
    
    -- 供应信息
    circulating_supply NUMERIC(30, 8),
    total_supply NUMERIC(30, 8),
    max_supply NUMERIC(30, 8),
    infinite_supply BOOLEAN DEFAULT FALSE,
    
    -- 时间信息
    last_updated TIMESTAMP WITH TIME ZONE,
    date_added TIMESTAMP WITH TIME ZONE,
    
    -- 标签信息（JSON格式存储）
    tags JSONB,
    
    -- 价格和市场信息
    price NUMERIC(20, 8),
    volume_24h NUMERIC(30, 8),
    volume_change_24h NUMERIC(10, 4),
    percent_change_1h NUMERIC(10, 4),
    percent_change_24h NUMERIC(10, 4),
    percent_change_7d NUMERIC(10, 4),
    market_cap NUMERIC(30, 8),
    market_cap_dominance NUMERIC(10, 4),
    fully_diluted_market_cap NUMERIC(30, 8),
    quote_last_updated TIMESTAMP WITH TIME ZONE,
    
    -- 数据采集时间戳
    data_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- 系统时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 唯一约束：同一加密货币的唯一标识
    UNIQUE (crypto_id, symbol)
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_market_crypto_crypto_id ON market_crypto_listings(crypto_id);
CREATE INDEX IF NOT EXISTS idx_market_crypto_symbol ON market_crypto_listings(symbol);
CREATE INDEX IF NOT EXISTS idx_market_crypto_cmc_rank ON market_crypto_listings(cmc_rank);
CREATE INDEX IF NOT EXISTS idx_market_crypto_data_timestamp ON market_crypto_listings(data_timestamp);
CREATE INDEX IF NOT EXISTS idx_market_crypto_price ON market_crypto_listings(price);
CREATE INDEX IF NOT EXISTS idx_market_crypto_market_cap ON market_crypto_listings(market_cap);
CREATE INDEX IF NOT EXISTS idx_market_crypto_last_updated ON market_crypto_listings(last_updated);

-- 创建GIN索引用于标签搜索
CREATE INDEX IF NOT EXISTS idx_market_crypto_tags ON market_crypto_listings USING GIN (tags);

-- 创建复合索引用于常用查询
CREATE INDEX IF NOT EXISTS idx_market_crypto_rank_timestamp ON market_crypto_listings(cmc_rank, data_timestamp);
CREATE INDEX IF NOT EXISTS idx_market_crypto_symbol_timestamp ON market_crypto_listings(symbol, data_timestamp);

-- 注释表结构
COMMENT ON TABLE market_crypto_listings IS '市场加密货币列表数据表';
COMMENT ON COLUMN market_crypto_listings.crypto_id IS '加密货币ID';
COMMENT ON COLUMN market_crypto_listings.name IS '加密货币名称';
COMMENT ON COLUMN market_crypto_listings.symbol IS '加密货币符号';
COMMENT ON COLUMN market_crypto_listings.slug IS 'URL slug';
COMMENT ON COLUMN market_crypto_listings.cmc_rank IS '市场排名';
COMMENT ON COLUMN market_crypto_listings.circulating_supply IS '流通供应量';
COMMENT ON COLUMN market_crypto_listings.total_supply IS '总供应量';
COMMENT ON COLUMN market_crypto_listings.max_supply IS '最大供应量';
COMMENT ON COLUMN market_crypto_listings.infinite_supply IS '是否无限供应';
COMMENT ON COLUMN market_crypto_listings.last_updated IS '数据最后更新时间';
COMMENT ON COLUMN market_crypto_listings.date_added IS '添加时间';
COMMENT ON COLUMN market_crypto_listings.tags IS '标签列表（JSON格式）';
COMMENT ON COLUMN market_crypto_listings.price IS '价格（USD）';
COMMENT ON COLUMN market_crypto_listings.volume_24h IS '24小时交易量';
COMMENT ON COLUMN market_crypto_listings.volume_change_24h IS '24小时交易量变化百分比';
COMMENT ON COLUMN market_crypto_listings.percent_change_1h IS '1小时价格变化百分比';
COMMENT ON COLUMN market_crypto_listings.percent_change_24h IS '24小时价格变化百分比';
COMMENT ON COLUMN market_crypto_listings.percent_change_7d IS '7天价格变化百分比';
COMMENT ON COLUMN market_crypto_listings.market_cap IS '市值';
COMMENT ON COLUMN market_crypto_listings.market_cap_dominance IS '市值占比';
COMMENT ON COLUMN market_crypto_listings.fully_diluted_market_cap IS '完全稀释市值';
COMMENT ON COLUMN market_crypto_listings.quote_last_updated IS '报价最后更新时间';
COMMENT ON COLUMN market_crypto_listings.data_timestamp IS '数据采集时间戳';