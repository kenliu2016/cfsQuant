-- 物化视图转换方案 - 数据迁移和同步脚本
-- 作者: AI Assistant
-- 创建时间: $(date)
-- 描述: 将现有视图数据迁移到新物化视图，并创建同步视图

-- 0. 设置事务和错误处理
BEGIN;

-- 1. 创建过渡视图（保持向后兼容）
-- 这些视图将作为新物化视图的包装器，确保现有应用无需修改

-- 1.1 创建3分钟K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_3m AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_3m_materialized
UNION ALL
-- 实时数据部分（用于最新时间段的数据）
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_3m_materialized)
GROUP BY bucket, coin_id;

-- 1.2 创建5分钟K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_5m AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_5m_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_5m_materialized)
GROUP BY bucket, coin_id;

-- 1.3 创建15分钟K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_15m AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_15m_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_15m_materialized)
GROUP BY bucket, coin_id;

-- 1.4 创建30分钟K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_30m AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_30m_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_30m_materialized)
GROUP BY bucket, coin_id;

-- 1.5 创建1小时K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_1h AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_1h_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_1h_materialized)
GROUP BY bucket, coin_id;

-- 1.6 创建2小时K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_2h AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_2h_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_2h_materialized)
GROUP BY bucket, coin_id;

-- 1.7 创建4小时K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_4h AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_4h_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_4h_materialized)
GROUP BY bucket, coin_id;

-- 1.8 创建1天K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_1d AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_1d_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_1d_materialized)
GROUP BY bucket, coin_id;

-- 1.9 创建2天K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_2d AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_2d_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_2d_materialized)
GROUP BY bucket, coin_id;

-- 1.10 创建3天K线过渡视图
CREATE OR REPLACE VIEW market_ohlcv_3d AS
SELECT 
    bucket as time,
    coin_id,
    open,
    high,
    low,
    close,
    volume,
    amount,
    vwap,
    trade_count
FROM market_ohlcv_3d_materialized
UNION ALL
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
WHERE time > (SELECT COALESCE(MAX(bucket), '1970-01-01') FROM market_ohlcv_3d_materialized)
GROUP BY bucket, coin_id;

-- 2. 初始化物化视图数据
-- 使用历史数据填充新创建的物化视图

-- 2.1 填充3分钟K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_3m_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '30 days'),
    NOW() - INTERVAL '5 minutes');

-- 2.2 填充5分钟K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_5m_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '60 days'),
    NOW() - INTERVAL '10 minutes');

-- 2.3 填充15分钟K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_15m_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '90 days'),
    NOW() - INTERVAL '30 minutes');

-- 2.4 填充30分钟K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_30m_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '120 days'),
    NOW() - INTERVAL '1 hour');

-- 2.5 填充1小时K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_1h_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '180 days'),
    NOW() - INTERVAL '2 hours');

-- 2.6 填充2小时K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_2h_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '240 days'),
    NOW() - INTERVAL '4 hours');

-- 2.7 填充4小时K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_4h_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '360 days'),
    NOW() - INTERVAL '8 hours');

-- 2.8 填充1天K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_1d_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '720 days'),
    NOW() - INTERVAL '1 day');

-- 2.9 填充2天K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_2d_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '1080 days'),
    NOW() - INTERVAL '2 days');

-- 2.10 填充3天K线物化视图
CALL refresh_continuous_aggregate('market_ohlcv_3d_materialized', 
    (SELECT MIN(time) FROM market_ohlcv_1m WHERE time >= NOW() - INTERVAL '1440 days'),
    NOW() - INTERVAL '3 days');

-- 3. 数据一致性验证
DO $$
DECLARE
    view_name TEXT;
    old_count BIGINT;
    new_count BIGINT;
    total_views INTEGER := 0;
    consistent_views INTEGER := 0;
BEGIN
    -- 验证每个视图的数据一致性
    FOR view_name IN (SELECT table_name FROM information_schema.views 
                      WHERE table_name LIKE 'market_ohlcv_%' AND table_schema = 'public') 
    LOOP
        total_views := total_views + 1;
        
        -- 获取旧视图数据量
        EXECUTE format('SELECT COUNT(*) FROM backup_data_sample_%s', 
                       SUBSTRING(view_name FROM 13)) INTO old_count;
        
        -- 获取新视图数据量
        EXECUTE format('SELECT COUNT(*) FROM %I', view_name) INTO new_count;
        
        IF old_count = new_count THEN
            consistent_views := consistent_views + 1;
            RAISE NOTICE '✅ 视图 % 数据一致性验证通过，数据量: %', view_name, new_count;
        ELSE
            RAISE WARNING '⚠️ 视图 % 数据不一致，旧数据: %, 新数据: %', view_name, old_count, new_count;
        END IF;
    END LOOP;
    
    RAISE NOTICE '数据一致性验证完成: 一致视图 %/%', consistent_views, total_views;
END $$;

COMMIT;

RAISE NOTICE '🎉 数据迁移和同步脚本执行完成！';
RAISE NOTICE '下一步: 运行回滚脚本（如果需要）或进行性能测试';