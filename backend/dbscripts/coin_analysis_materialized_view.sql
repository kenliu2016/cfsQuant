-- 币种分析表专用物化视图创建脚本
-- 该视图优化币种分析数据的查询性能

-- 创建币种分析专用物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS coin_analysis_view
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
WITH latest_ohlcv AS (
    SELECT 
        symbol,
        market_cap,
        quote_volume,
        vmr,
        bucket,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
    FROM market_ohlcv_1d
    WHERE market_cap > 100000000
        AND bucket >= NOW() - INTERVAL '7 days'
),
latest_ve AS (
    SELECT 
        symbol,
        ve,
        datetime,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY datetime DESC) as rn
    FROM indecator_ve
    WHERE datetime >= NOW() - INTERVAL '7 days'
)
SELECT 
    mc.symbol,
    mc.exchange,
    mc.active,
    mc.quotecurrency,
    lo.market_cap,
    lo.quote_volume,
    lo.vmr,
    lv.ve,
    lo.bucket as last_ohlcv_time,
    lv.datetime as last_ve_time,
    NOW() as view_refresh_time
FROM market_codes mc
INNER JOIN latest_ohlcv lo ON mc.symbol = lo.symbol AND lo.rn = 1
LEFT JOIN latest_ve lv ON mc.symbol = lv.symbol AND lv.rn = 1
WHERE mc.active = true
    AND mc.quotecurrency = 'USDT'
WITH DATA;

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_coin_analysis_symbol 
    ON coin_analysis_view(symbol);
    
CREATE INDEX IF NOT EXISTS idx_coin_analysis_market_cap 
    ON coin_analysis_view(market_cap DESC);
    
CREATE INDEX IF NOT EXISTS idx_coin_analysis_active 
    ON coin_analysis_view(active);

-- 添加连续聚合策略，每15分钟刷新一次
SELECT add_continuous_aggregate_policy(
    'coin_analysis_view',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '15 minutes'
);

-- 视图注释
COMMENT ON MATERIALIZED VIEW coin_analysis_view IS '币种分析表专用物化视图，优化查询性能';
COMMENT ON COLUMN coin_analysis_view.symbol IS '币种代码';
COMMENT ON COLUMN coin_analysis_view.market_cap IS '市值';
COMMENT ON COLUMN coin_analysis_view.quote_volume IS '24小时成交量';
COMMENT ON COLUMN coin_analysis_view.vmr IS '成交量市值比率';
COMMENT ON COLUMN coin_analysis_view.ve IS '波动率效率指标';

-- 创建刷新函数
CREATE OR REPLACE FUNCTION refresh_coin_analysis_view()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY coin_analysis_view;
END;
$$ LANGUAGE plpgsql;

-- 创建手动刷新视图的存储过程
CREATE OR REPLACE PROCEDURE manual_refresh_coin_analysis()
LANGUAGE plpgsql
AS $$
BEGIN
    CALL refresh_coin_analysis_view();
    RAISE NOTICE '币种分析视图已手动刷新';
END;
$$;