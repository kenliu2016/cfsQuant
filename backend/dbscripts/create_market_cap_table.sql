-- 加密货币市值数据表
-- 用于存储CoinMarketCap网站上加密货币的市值和价格数据

CREATE TABLE IF NOT EXISTS market_cap (
    id SERIAL PRIMARY KEY,
    crypto_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    cmc_rank INTEGER NOT NULL,
    
    -- 市值信息
    market_cap NUMERIC(30, 8),
    market_cap_dominance NUMERIC(10, 4),
    
    -- 价格信息
    price NUMERIC(20, 8),
    price_change_1h NUMERIC(10, 4),
    price_change_24h NUMERIC(10, 4),
    price_change_7d NUMERIC(10, 4),
    
    -- 供应信息
    circulating_supply NUMERIC(30, 8),
    total_supply NUMERIC(30, 8),
    max_supply NUMERIC(30, 8),
    
    -- 交易量信息
    volume_24h NUMERIC(30, 8),
    volume_change_24h NUMERIC(10, 4),
    
    -- 时间信息
    last_updated TIMESTAMP WITH TIME ZONE,
    date_added TIMESTAMP WITH TIME ZONE,
    
    -- 数据采集时间戳
    data_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- 系统时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 唯一约束：同一加密货币在同一时间点的数据
    UNIQUE (crypto_id, data_timestamp)
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_market_cap_crypto_id ON market_cap(crypto_id);
CREATE INDEX IF NOT EXISTS idx_market_cap_symbol ON market_cap(symbol);
CREATE INDEX IF NOT EXISTS idx_market_cap_cmc_rank ON market_cap(cmc_rank);
CREATE INDEX IF NOT EXISTS idx_market_cap_market_cap ON market_cap(market_cap);
CREATE INDEX IF NOT EXISTS idx_market_cap_price ON market_cap(price);
CREATE INDEX IF NOT EXISTS idx_market_cap_data_timestamp ON market_cap(data_timestamp);
CREATE INDEX IF NOT EXISTS idx_market_cap_last_updated ON market_cap(last_updated);

-- 创建复合索引用于常用查询
CREATE INDEX IF NOT EXISTS idx_market_cap_rank_timestamp ON market_cap(cmc_rank, data_timestamp);
CREATE INDEX IF NOT EXISTS idx_market_cap_symbol_timestamp ON market_cap(symbol, data_timestamp);

-- 注释表结构
COMMENT ON TABLE market_cap IS '加密货币市值数据表';
COMMENT ON COLUMN market_cap.crypto_id IS '加密货币ID';
COMMENT ON COLUMN market_cap.name IS '加密货币名称';
COMMENT ON COLUMN market_cap.symbol IS '加密货币符号';
COMMENT ON COLUMN market_cap.cmc_rank IS 'CMC排名';
COMMENT ON COLUMN market_cap.market_cap IS '市值（USD）';
COMMENT ON COLUMN market_cap.market_cap_dominance IS '市值占比';
COMMENT ON COLUMN market_cap.price IS '价格（USD）';
COMMENT ON COLUMN market_cap.price_change_1h IS '1小时价格变化百分比';
COMMENT ON COLUMN market_cap.price_change_24h IS '24小时价格变化百分比';
COMMENT ON COLUMN market_cap.price_change_7d IS '7天价格变化百分比';
COMMENT ON COLUMN market_cap.circulating_supply IS '流通供应量';
COMMENT ON COLUMN market_cap.total_supply IS '总供应量';
COMMENT ON COLUMN market_cap.max_supply IS '最大供应量';
COMMENT ON COLUMN market_cap.volume_24h IS '24小时交易量';
COMMENT ON COLUMN market_cap.volume_change_24h IS '24小时交易量变化百分比';
COMMENT ON COLUMN market_cap.last_updated IS '数据最后更新时间';
COMMENT ON COLUMN market_cap.date_added IS '添加时间';
COMMENT ON COLUMN market_cap.data_timestamp IS '数据采集时间戳';