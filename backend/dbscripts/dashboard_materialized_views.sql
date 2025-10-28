-- Dashboard物化视图创建脚本
-- 该脚本创建用于dashboard页面的高性能物化视图
-- 基于TimescaleDB连续聚合功能，提供实时优化的数据查询性能

-- ============ Dashboard市场情绪物化视图 ============
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_market_sentiment
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
WITH market_stats AS (
    -- 获取24小时内币种涨跌统计
    SELECT 
        COUNT(*) as total_coins,
        COUNT(CASE WHEN return_pct > 0 THEN 1 END) as rising_coins,
        COUNT(CASE WHEN return_pct < 0 THEN 1 END) as falling_coins,
        AVG(return_pct) as avg_gain_24h
    FROM market_ohlcv_1d
    WHERE bucket >= NOW() - INTERVAL '1 day'
        AND market_cap > 100000000
),
bull_bear_data AS (
    -- 获取最新牛熊市指标
    SELECT 
        score as bull_bear_score,
        updated_at
    FROM indecator_bull_bear
    ORDER BY updated_at DESC
    LIMIT 1
),
fear_greed_data AS (
    -- 获取最新恐惧贪婪指数
    SELECT 
        value as fear_greed_index,
        updated_at
    FROM indecator_fear_greed
    ORDER BY updated_at DESC
    LIMIT 1
)
SELECT 
    ms.total_coins,
    ms.rising_coins,
    ms.falling_coins,
    ms.avg_gain_24h,
    COALESCE(bb.bull_bear_score, 0.0) as bull_bear_score,
    COALESCE(fg.fear_greed_index, 50.0) as fear_greed_index,
    GREATEST(bb.updated_at, fg.updated_at) as last_updated,
    NOW() as view_refresh_time
FROM market_stats ms
CROSS JOIN bull_bear_data bb
CROSS JOIN fear_greed_data fg
WITH DATA;

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_dashboard_market_sentiment_last_updated 
    ON dashboard_market_sentiment(last_updated DESC);

-- 添加连续聚合策略，每15分钟刷新一次
SELECT add_continuous_aggregate_policy(
    'dashboard_market_sentiment',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '15 minutes'
);

-- ============ Dashboard强势弱势币种物化视图 ============
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_strong_weak_coins
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
WITH latest_prices AS (
    -- 获取最新价格和24小时涨跌幅
    SELECT 
        symbol,
        close as current_price,
        return_pct as gain_24h,
        vmr as vmr_24h,
        bucket
    FROM market_ohlcv_1d
    WHERE bucket >= NOW() - INTERVAL '1 day'
        AND market_cap > 100000000
        AND close > 0
),
latest_ve AS (
    -- 获取最新VE指标
    SELECT 
        symbol,
        ve,
        datetime
    FROM indecator_ve
    WHERE datetime >= NOW() - INTERVAL '1 day'
        AND timeframe = '1h'
),
ranked_coins AS (
    -- 为每个币种获取最新数据并计算综合评分
    SELECT 
        lp.symbol,
        lp.current_price,
        lp.gain_24h,
        lp.vmr_24h,
        lv.ve,
        -- 综合评分：涨跌幅权重40%，VE指标权重30%，VMR权重30%
        (COALESCE(lp.gain_24h, 0) * 0.4 + 
         COALESCE(lv.ve, 1.0) * 30 + 
         COALESCE(lp.vmr_24h, 0) * 0.3) as composite_score,
        ROW_NUMBER() OVER (PARTITION BY lp.symbol ORDER BY lp.bucket DESC, lv.datetime DESC) as rn
    FROM latest_prices lp
    LEFT JOIN latest_ve lv ON lp.symbol = lv.symbol
)
SELECT 
    symbol,
    current_price,
    gain_24h,
    vmr_24h,
    ve,
    composite_score,
    NOW() as view_refresh_time
FROM ranked_coins
WHERE rn = 1
    AND gain_24h IS NOT NULL
    AND current_price > 0
WITH DATA;

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_dashboard_strong_weak_coins_gain_24h 
    ON dashboard_strong_weak_coins(gain_24h DESC);
    
CREATE INDEX IF NOT EXISTS idx_dashboard_strong_weak_coins_composite_score 
    ON dashboard_strong_weak_coins(composite_score DESC);

-- 添加连续聚合策略，每15分钟刷新一次
SELECT add_continuous_aggregate_policy(
    'dashboard_strong_weak_coins',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '15 minutes'
);

-- ============ Dashboard币种分析物化视图 ============
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_coin_analysis
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
WITH market_data AS (
    -- 获取市场数据
    SELECT 
        symbol,
        close as current_price,
        market_cap,
        quote_volume as total_volume_24h,
        vmr as vmr_24h,
        bucket
    FROM market_ohlcv_1d
    WHERE bucket >= NOW() - INTERVAL '1 day'
        AND market_cap > 100000000
),
ve_data AS (
    -- 获取VE指标数据
    SELECT 
        symbol,
        ve as ve_1h,
        actual_volatility,
        volume_efficiency,
        datetime
    FROM indecator_ve
    WHERE datetime >= NOW() - INTERVAL '1 day'
        AND timeframe = '1h'
),
combined_data AS (
    -- 合并市场数据和VE指标
    SELECT 
        md.symbol,
        md.current_price,
        md.market_cap,
        md.total_volume_24h,
        md.vmr_24h,
        vd.ve_1h,
        vd.actual_volatility,
        vd.volume_efficiency,
        -- 综合评分：市值权重25%，成交量权重25%，VE指标权重25%，VMR权重25%
        (LOG(COALESCE(md.market_cap, 1)) * 0.25 +
         LOG(COALESCE(md.total_volume_24h, 1)) * 0.25 +
         COALESCE(vd.ve_1h, 1.0) * 25 +
         COALESCE(md.vmr_24h, 0) * 0.25) as composite_score,
        ROW_NUMBER() OVER (PARTITION BY md.symbol ORDER BY md.bucket DESC, vd.datetime DESC) as rn
    FROM market_data md
    LEFT JOIN ve_data vd ON md.symbol = vd.symbol
)
SELECT 
    symbol,
    current_price,
    market_cap,
    total_volume_24h,
    vmr_24h,
    ve_1h,
    actual_volatility,
    volume_efficiency,
    composite_score,
    ROW_NUMBER() OVER (ORDER BY composite_score DESC) as rank,
    NOW() as view_refresh_time
FROM combined_data
WHERE rn = 1
    AND current_price > 0
    AND market_cap > 0
WITH DATA;

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_dashboard_coin_analysis_composite_score 
    ON dashboard_coin_analysis(composite_score DESC);
    
CREATE INDEX IF NOT EXISTS idx_dashboard_coin_analysis_market_cap 
    ON dashboard_coin_analysis(market_cap DESC);

-- 添加连续聚合策略，每15分钟刷新一次
SELECT add_continuous_aggregate_policy(
    'dashboard_coin_analysis',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '15 minutes'
);

-- ============ Dashboard汇总物化视图 ============
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_summary_view
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
WITH market_sentiment AS (
    -- 获取市场情绪数据
    SELECT * FROM dashboard_market_sentiment
    ORDER BY last_updated DESC
    LIMIT 1
),
strong_coins AS (
    -- 获取强势币种（涨跌幅前20）
    SELECT 
        symbol,
        current_price,
        gain_24h,
        vmr_24h,
        ve,
        composite_score
    FROM dashboard_strong_weak_coins
    WHERE gain_24h > 0
    ORDER BY gain_24h DESC
    LIMIT 20
),
weak_coins AS (
    -- 获取弱势币种（涨跌幅后20）
    SELECT 
        symbol,
        current_price,
        gain_24h,
        vmr_24h,
        ve,
        composite_score
    FROM dashboard_strong_weak_coins
    WHERE gain_24h < 0
    ORDER BY gain_24h ASC
    LIMIT 20
),
coin_analysis AS (
    -- 获取币种分析数据（综合评分前30）
    SELECT 
        symbol,
        current_price,
        market_cap,
        total_volume_24h,
        vmr_24h,
        ve_1h as ve_value,
        actual_volatility,
        volume_efficiency,
        composite_score,
        rank
    FROM dashboard_coin_analysis
    ORDER BY composite_score DESC
    LIMIT 300
)
SELECT 
    -- 市场情绪数据
    ms.total_coins,
    ms.rising_coins,
    ms.falling_coins,
    ms.avg_gain_24h,
    ms.bull_bear_score,
    ms.fear_greed_index,
    ms.last_updated,
    
    -- 强势弱势币种数据
    ARRAY_TO_JSON(ARRAY_AGG(
        JSON_BUILD_OBJECT(
            'symbol', sc.symbol,
            'current_price', sc.current_price,
            'gain_24h', sc.gain_24h,
            'vmr_24h', sc.vmr_24h,
            've', sc.ve,
            'composite_score', sc.composite_score
        ) ORDER BY sc.gain_24h DESC
    )) FILTER (WHERE sc.symbol IS NOT NULL) as strong_coins,
    
    ARRAY_TO_JSON(ARRAY_AGG(
        JSON_BUILD_OBJECT(
            'symbol', wc.symbol,
            'current_price', wc.current_price,
            'gain_24h', wc.gain_24h,
            'vmr_24h', wc.vmr_24h,
            've', wc.ve,
            'composite_score', wc.composite_score
        ) ORDER BY wc.gain_24h ASC
    )) FILTER (WHERE wc.symbol IS NOT NULL) as weak_coins,
    
    -- 币种分析数据
    ARRAY_TO_JSON(ARRAY_AGG(
        JSON_BUILD_OBJECT(
            'symbol', ca.symbol,
            'current_price', ca.current_price,
            'market_cap', ca.market_cap,
            'volume_24h', ca.total_volume_24h,
            'vmr', ca.vmr_24h,
            've_value', ca.ve_value,
            'actual_volatility', ca.actual_volatility,
            'composite_score', ca.composite_score,
            'rank', ca.rank
        ) ORDER BY ca.composite_score DESC
    )) FILTER (WHERE ca.symbol IS NOT NULL) as coin_analysis,
    
    -- 元数据
    NOW() as last_updated,
    'materialized_view' as data_source
FROM market_sentiment ms
LEFT JOIN strong_coins sc ON true
LEFT JOIN weak_coins wc ON true
LEFT JOIN coin_analysis ca ON true
GROUP BY 
    ms.total_coins, ms.rising_coins, ms.falling_coins, ms.avg_gain_24h,
    ms.bull_bear_score, ms.fear_greed_index, ms.last_updated
WITH DATA;

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_dashboard_summary_view_last_updated 
    ON dashboard_summary_view(last_updated DESC);

-- 添加连续聚合策略，每15分钟刷新一次
SELECT add_continuous_aggregate_policy(
    'dashboard_summary_view',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '15 minutes'
);

-- ============ 视图注释和说明 ============

-- Dashboard市场情绪视图注释
COMMENT ON MATERIALIZED VIEW dashboard_market_sentiment IS 'Dashboard市场情绪物化视图，提供实时市场情绪指标数据';
COMMENT ON COLUMN dashboard_market_sentiment.total_coins IS '总币种数量';
COMMENT ON COLUMN dashboard_market_sentiment.rising_coins IS '上涨币种数量';
COMMENT ON COLUMN dashboard_market_sentiment.falling_coins IS '下跌币种数量';
COMMENT ON COLUMN dashboard_market_sentiment.avg_gain_24h IS '24小时平均涨跌幅';
COMMENT ON COLUMN dashboard_market_sentiment.bull_bear_score IS '牛熊市分数';
COMMENT ON COLUMN dashboard_market_sentiment.fear_greed_index IS '恐惧贪婪指数';

-- Dashboard强势弱势币种视图注释
COMMENT ON MATERIALIZED VIEW dashboard_strong_weak_coins IS 'Dashboard强势弱势币种物化视图，提供币种涨跌幅和综合评分数据';
COMMENT ON COLUMN dashboard_strong_weak_coins.symbol IS '币种代码';
COMMENT ON COLUMN dashboard_strong_weak_coins.current_price IS '当前价格';
COMMENT ON COLUMN dashboard_strong_weak_coins.gain_24h IS '24小时涨跌幅';
COMMENT ON COLUMN dashboard_strong_weak_coins.vmr_24h IS '24小时成交量市值比率';
COMMENT ON COLUMN dashboard_strong_weak_coins.ve IS '波动率效率指标';
COMMENT ON COLUMN dashboard_strong_weak_coins.composite_score IS '综合评分';

-- Dashboard币种分析视图注释
COMMENT ON MATERIALIZED VIEW dashboard_coin_analysis IS 'Dashboard币种分析物化视图，提供币种详细分析数据';
COMMENT ON COLUMN dashboard_coin_analysis.symbol IS '币种代码';
COMMENT ON COLUMN dashboard_coin_analysis.current_price IS '当前价格';
COMMENT ON COLUMN dashboard_coin_analysis.market_cap IS '市值';
COMMENT ON COLUMN dashboard_coin_analysis.total_volume_24h IS '24小时成交量';
COMMENT ON COLUMN dashboard_coin_analysis.vmr_24h IS '24小时成交量市值比率';
COMMENT ON COLUMN dashboard_coin_analysis.ve_1h IS '1小时波动率效率指标';
COMMENT ON COLUMN dashboard_coin_analysis.composite_score IS '综合评分';

-- Dashboard汇总视图注释
COMMENT ON MATERIALIZED VIEW dashboard_summary_view IS 'Dashboard汇总物化视图，整合所有dashboard相关数据';
COMMENT ON COLUMN dashboard_summary_view.strong_coins IS '强势币种列表（JSON格式）';
COMMENT ON COLUMN dashboard_summary_view.weak_coins IS '弱势币种列表（JSON格式）';
COMMENT ON COLUMN dashboard_summary_view.coin_analysis IS '币种分析列表（JSON格式）';

-- ============ 刷新函数和存储过程 ============

-- 创建手动刷新所有dashboard视图的函数
CREATE OR REPLACE FUNCTION refresh_all_dashboard_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_market_sentiment;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_strong_weak_coins;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_coin_analysis;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_summary_view;
    RAISE NOTICE '所有Dashboard物化视图已刷新';
END;
$$ LANGUAGE plpgsql;

-- 创建手动刷新存储过程
CREATE OR REPLACE PROCEDURE manual_refresh_dashboard_views()
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM refresh_all_dashboard_views();
END;
$$;

-- ============ 使用说明 ============

-- 1. 执行此脚本创建所有dashboard物化视图
-- 2. 视图会自动每15分钟刷新一次
-- 3. 可以手动调用刷新函数：CALL manual_refresh_dashboard_views();
-- 4. 查询dashboard汇总数据：SELECT * FROM dashboard_summary_view ORDER BY last_updated DESC LIMIT 1;

-- ============ 清理脚本（可选） ============

-- 如果需要清理所有dashboard物化视图，可以执行以下脚本：
-- DROP MATERIALIZED VIEW IF EXISTS dashboard_summary_view;
-- DROP MATERIALIZED VIEW IF EXISTS dashboard_coin_analysis;
-- DROP MATERIALIZED VIEW IF EXISTS dashboard_strong_weak_coins;
-- DROP MATERIALIZED VIEW IF EXISTS dashboard_market_sentiment;
-- DROP FUNCTION IF EXISTS refresh_all_dashboard_views();
-- DROP PROCEDURE IF EXISTS manual_refresh_dashboard_views();