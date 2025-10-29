-- 物化视图转换方案 - 主转换脚本
-- 作者: AI Assistant
-- 创建时间: $(date)
-- 描述: 将market_ohlcv_*普通视图转换为TimescaleDB连续聚合物化视图

-- 0. 设置事务和错误处理
BEGIN;

-- 1. 创建新的物化视图（基于TimescaleDB连续聚合）
-- 使用连续聚合替代普通视图，提供更好的性能

-- 1.1 创建3分钟K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_3m_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('3 minutes', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '30 days'  -- 保留30天数据
GROUP BY bucket, coin_id
WITH NO DATA;

-- 为物化视图创建索引
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_3m_materialized_bucket 
ON market_ohlcv_3m_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_3m_materialized_coin 
ON market_ohlcv_3m_materialized (coin_id, bucket DESC);

-- 1.2 创建5分钟K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_5m_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('5 minutes', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '60 days'  -- 保留60天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_5m_materialized_bucket 
ON market_ohlcv_5m_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_5m_materialized_coin 
ON market_ohlcv_5m_materialized (coin_id, bucket DESC);

-- 1.3 创建15分钟K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_15m_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('15 minutes', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '90 days'  -- 保留90天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_15m_materialized_bucket 
ON market_ohlcv_15m_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_15m_materialized_coin 
ON market_ohlcv_15m_materialized (coin_id, bucket DESC);

-- 1.4 创建30分钟K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_30m_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('30 minutes', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '120 days'  -- 保留120天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_30m_materialized_bucket 
ON market_ohlcv_30m_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_30m_materialized_coin 
ON market_ohlcv_30m_materialized (coin_id, bucket DESC);

-- 1.5 创建1小时K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_1h_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '180 days'  -- 保留180天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_1h_materialized_bucket 
ON market_ohlcv_1h_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_1h_materialized_coin 
ON market_ohlcv_1h_materialized (coin_id, bucket DESC);

-- 1.6 创建2小时K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_2h_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('2 hours', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '240 days'  -- 保留240天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_2h_materialized_bucket 
ON market_ohlcv_2h_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_2h_materialized_coin 
ON market_ohlcv_2h_materialized (coin_id, bucket DESC);

-- 1.7 创建4小时K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_4h_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('4 hours', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '360 days'  -- 保留360天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_4h_materialized_bucket 
ON market_ohlcv_4h_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_4h_materialized_coin 
ON market_ohlcv_4h_materialized (coin_id, bucket DESC);

-- 1.8 创建1天K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_1d_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '720 days'  -- 保留720天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_1d_materialized_bucket 
ON market_ohlcv_1d_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_1d_materialized_coin 
ON market_ohlcv_1d_materialized (coin_id, bucket DESC);

-- 1.9 创建2天K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_2d_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('2 days', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '1080 days'  -- 保留1080天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_2d_materialized_bucket 
ON market_ohlcv_2d_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_2d_materialized_coin 
ON market_ohlcv_2d_materialized (coin_id, bucket DESC);

-- 1.10 创建3天K线物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_3d_materialized
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('3 days', time) as bucket,
    coin_id,
    first(open, time) as open,
    max(high) as high,
    min(low) as low,
    last(close, time) as close,
    sum(volume) as volume,
    sum(amount) as amount,
    avg(vwap) as vwap,
    count(*) as trade_count
FROM market_ohlcv_1m
WHERE time >= NOW() - INTERVAL '1440 days'  -- 保留1440天数据
GROUP BY bucket, coin_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_3d_materialized_bucket 
ON market_ohlcv_3d_materialized (bucket DESC);
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_3d_materialized_coin 
ON market_ohlcv_3d_materialized (coin_id, bucket DESC);

-- 2. 设置连续聚合策略
-- 为每个物化视图设置自动刷新策略

-- 2.1 设置3分钟K线刷新策略（每2分钟刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_3m_materialized',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '2 minutes',
    schedule_interval => INTERVAL '2 minutes');

-- 2.2 设置5分钟K线刷新策略（每4分钟刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_5m_materialized',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '4 minutes',
    schedule_interval => INTERVAL '4 minutes');

-- 2.3 设置15分钟K线刷新策略（每14分钟刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_15m_materialized',
    start_offset => INTERVAL '6 hours',
    end_offset => INTERVAL '14 minutes',
    schedule_interval => INTERVAL '14 minutes');

-- 2.4 设置30分钟K线刷新策略（每29分钟刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_30m_materialized',
    start_offset => INTERVAL '12 hours',
    end_offset => INTERVAL '29 minutes',
    schedule_interval => INTERVAL '29 minutes');

-- 2.5 设置1小时K线刷新策略（每59分钟刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_1h_materialized',
    start_offset => INTERVAL '24 hours',
    end_offset => INTERVAL '59 minutes',
    schedule_interval => INTERVAL '59 minutes');

-- 2.6 设置2小时K线刷新策略（每1小时刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_2h_materialized',
    start_offset => INTERVAL '48 hours',
    end_offset => INTERVAL '1 hours',
    schedule_interval => INTERVAL '1 hours');

-- 2.7 设置4小时K线刷新策略（每2小时刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_4h_materialized',
    start_offset => INTERVAL '96 hours',
    end_offset => INTERVAL '2 hours',
    schedule_interval => INTERVAL '2 hours');

-- 2.8 设置1天K线刷新策略（每23小时刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_1d_materialized',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '23 hours',
    schedule_interval => INTERVAL '23 hours');

-- 2.9 设置2天K线刷新策略（每1天刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_2d_materialized',
    start_offset => INTERVAL '14 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- 2.10 设置3天K线刷新策略（每1天刷新）
SELECT add_continuous_aggregate_policy('market_ohlcv_3d_materialized',
    start_offset => INTERVAL '21 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- 3. 验证物化视图创建
DO $$
DECLARE
    mv_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO mv_count FROM timescaledb_information.continuous_aggregates 
    WHERE view_name LIKE 'market_ohlcv_%_materialized';
    
    IF mv_count = 10 THEN
        RAISE NOTICE '✅ 所有10个物化视图创建成功';
    ELSE
        RAISE WARNING '⚠️ 物化视图创建数量不匹配，实际: %', mv_count;
    END IF;
END $$;

COMMIT;

RAISE NOTICE '🎉 物化视图转换脚本执行完成！';
RAISE NOTICE '下一步: 运行数据迁移脚本将现有数据迁移到新物化视图';