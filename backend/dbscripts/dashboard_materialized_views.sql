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
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_strong_weak_coins AS
WITH hourly_data AS (
    -- 获取每个symbol的最新24小时数据
    SELECT 
        symbol,
        bucket,
        close,
        open,
        quote_volume,
        market_cap,
        vmr,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
    FROM market_ohlcv_1h
    WHERE bucket >= NOW() - INTERVAL '24 hours'
        AND market_cap > 100000000
        AND close > 0
),
latest_15m AS (
    -- 获取每个symbol的最新15分钟数据
    SELECT 
        symbol,
        vmr as vmr_15m,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
    FROM market_ohlcv_15m
    WHERE bucket >= NOW() - INTERVAL '1 hour'
        AND market_cap > 100000000
        AND close > 0
),
latest_1h AS (
    -- 获取每个symbol的最新1小时数据
    SELECT 
        symbol,
        vmr as vmr_1h,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
    FROM market_ohlcv_1h
    WHERE bucket >= NOW() - INTERVAL '1 hour'
        AND market_cap > 100000000
        AND close > 0
),
latest_1d AS (
    -- 获取每个symbol的最新1天数据
    SELECT 
        symbol,
        vmr as vmr_1d,
        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket DESC) as rn
    FROM market_ohlcv_1d
    WHERE bucket >= NOW() - INTERVAL '1 day'
        AND market_cap > 100000000
        AND close > 0
),
coin_24h_stats AS (
    -- 计算24小时统计指标
    SELECT 
        hd.symbol,
        -- 24h_VMR计算：24小时内总成交量 / 期初市值
        SUM(hd.quote_volume) / 
        (SELECT market_cap FROM hourly_data 
         WHERE symbol = hd.symbol AND rn = 24) as vmr_24h,
        
        -- 24h_gain计算：(当前收盘价 - 24小时前开盘价) / 24小时前开盘价
        (MAX(CASE WHEN hd.rn = 1 THEN hd.close END) - 
         MIN(CASE WHEN hd.rn = 24 THEN hd.open END)) / 
         MIN(CASE WHEN hd.rn = 24 THEN hd.open END) as gain_24h,
        
        -- 获取当前价格
        MAX(CASE WHEN hd.rn = 1 THEN hd.close END) as current_price,
        
        -- 获取24小时数据用于图表
        JSON_AGG(
            JSON_BUILD_OBJECT(
                'bucket', hd.bucket,
                'close', hd.close,
                'quote_volume', hd.quote_volume
            ) ORDER BY hd.bucket DESC
        ) as hourly_chart_data
    FROM hourly_data hd
    WHERE hd.rn <= 24
    GROUP BY hd.symbol
    HAVING COUNT(*) = 24  -- 确保有完整的24小时数据
),
combined_scores AS (
    -- 组合所有分数
    SELECT 
        cs.symbol,
        cs.current_price,
        cs.vmr_24h,
        cs.gain_24h,
        cs.hourly_chart_data,
        COALESCE(l15.vmr_15m, 0) as vmr_15m,
        COALESCE(l1h.vmr_1h, 0) as vmr_1h,
        COALESCE(l1d.vmr_1d, 0) as vmr_1d,
        -- 复合分数计算
        (COALESCE(l15.vmr_15m, 0) * 0.1 + 
         COALESCE(l1h.vmr_1h, 0) * 0.3 + 
         COALESCE(l1d.vmr_1d, 0) * 0.6) as total_score
    FROM coin_24h_stats cs
    LEFT JOIN latest_15m l15 ON cs.symbol = l15.symbol AND l15.rn = 1
    LEFT JOIN latest_1h l1h ON cs.symbol = l1h.symbol AND l1h.rn = 1
    LEFT JOIN latest_1d l1d ON cs.symbol = l1d.symbol AND l1d.rn = 1
    WHERE cs.current_price > 0
        AND cs.vmr_24h IS NOT NULL
        AND cs.gain_24h IS NOT NULL
),
ranked_coins AS (
    -- 先按total_score排名前20
    SELECT 
        symbol,
        current_price,
        vmr_24h,
        gain_24h,
        vmr_15m,
        vmr_1h,
        vmr_1d,
        total_score,
        hourly_chart_data,
        ROW_NUMBER() OVER (ORDER BY total_score DESC) as total_score_rank
    FROM combined_scores
    ORDER BY total_score DESC
    LIMIT 20
),
ranked_coins_with_gain AS (
    -- 在前20个币种中按24h_gain排序，重新计算gain_rank（1-20）
    SELECT 
        rc.*,
        ROW_NUMBER() OVER (ORDER BY rc.gain_24h DESC) as gain_rank
    FROM ranked_coins rc
),
final_result AS (
    -- 最终结果，按24h_gain降序排序（1-5为强势币，20-16为弱势币）
    SELECT 
        rcg.symbol,
        rcg.current_price,
        rcg.vmr_24h,
        rcg.gain_24h,
        rcg.vmr_15m,
        rcg.vmr_1h,
        rcg.vmr_1d,
        rcg.total_score,
        rcg.hourly_chart_data,
        rcg.total_score_rank,
        rcg.gain_rank,
        CASE 
            WHEN rcg.gain_rank <= 5 THEN '强势币'
            WHEN rcg.gain_rank >= 16 AND rcg.gain_rank <= 20 THEN '弱势币'
            ELSE '中性币'
        END as coin_type,
        NOW() as view_refresh_time
    FROM ranked_coins_with_gain rcg
    ORDER BY rcg.gain_rank ASC  -- 按gain_rank升序排列（gain_rank越小，24h_gain越大）
)
SELECT * FROM final_result
WITH DATA;

-- 创建唯一索引以支持并发刷新
CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_strong_weak_coins_unique 
    ON dashboard_strong_weak_coins(symbol);

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_dashboard_strong_weak_coins_total_score 
    ON dashboard_strong_weak_coins(total_score DESC);
    
CREATE INDEX IF NOT EXISTS idx_dashboard_strong_weak_coins_gain_24h 
    ON dashboard_strong_weak_coins(gain_24h DESC);

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
        -- 综合评分：24h_vmr * 0.4 + 1h_ve * 0.6
        (COALESCE(md.vmr_24h, 0) * 0.4 +
         COALESCE(vd.ve_1h, 0) * 0.6) as composite_score,
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
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_summary_view AS
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
        total_score as composite_score
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
        total_score as composite_score
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
    
    -- 强势弱势币种数据
    COALESCE(JSON_AGG(
        JSON_BUILD_OBJECT(
            'symbol', sc.symbol,
            'current_price', sc.current_price,
            'gain_24h', sc.gain_24h,
            'vmr_24h', sc.vmr_24h,
            'composite_score', sc.composite_score
        ) ORDER BY sc.gain_24h DESC
    ) FILTER (WHERE sc.symbol IS NOT NULL), '[]'::json) as strong_coins,
    
    COALESCE(JSON_AGG(
        JSON_BUILD_OBJECT(
            'symbol', wc.symbol,
            'current_price', wc.current_price,
            'gain_24h', wc.gain_24h,
            'vmr_24h', wc.vmr_24h,
            'composite_score', wc.composite_score
        ) ORDER BY wc.gain_24h ASC
    ) FILTER (WHERE wc.symbol IS NOT NULL), '[]'::json) as weak_coins,
    
    -- 币种分析数据
    COALESCE(JSON_AGG(
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
    ) FILTER (WHERE ca.symbol IS NOT NULL), '[]'::json) as coin_analysis,
    
    -- 元数据
    NOW() as last_updated,
    'materialized_view' as data_source
FROM market_sentiment ms
LEFT JOIN strong_coins sc ON true
LEFT JOIN weak_coins wc ON true
LEFT JOIN coin_analysis ca ON true
GROUP BY 
    ms.total_coins, ms.rising_coins, ms.falling_coins, ms.avg_gain_24h,
    ms.bull_bear_score, ms.fear_greed_index
WITH DATA;

-- 创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_dashboard_summary_view_last_updated 
    ON dashboard_summary_view(last_updated DESC);

-- 添加刷新策略，每15分钟刷新一次
-- 注意：dashboard_summary_view不是连续聚合视图，需要手动刷新
-- 可以使用定时任务或外部调度器定期调用：REFRESH MATERIALIZED VIEW dashboard_summary_view;

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
COMMENT ON MATERIALIZED VIEW dashboard_strong_weak_coins IS '强弱势币增强版物化视图，符合特定逻辑要求的币种分析';
COMMENT ON COLUMN dashboard_strong_weak_coins.symbol IS '币种代码';
COMMENT ON COLUMN dashboard_strong_weak_coins.current_price IS '当前价格';
COMMENT ON COLUMN dashboard_strong_weak_coins.vmr_24h IS '24小时成交量市值比率';
COMMENT ON COLUMN dashboard_strong_weak_coins.gain_24h IS '24小时涨跌幅';
COMMENT ON COLUMN dashboard_strong_weak_coins.vmr_15m IS '15分钟成交量市值比率';
COMMENT ON COLUMN dashboard_strong_weak_coins.vmr_1h IS '1小时成交量市值比率';
COMMENT ON COLUMN dashboard_strong_weak_coins.vmr_1d IS '1天成交量市值比率';
COMMENT ON COLUMN dashboard_strong_weak_coins.total_score IS '复合分数';
COMMENT ON COLUMN dashboard_strong_weak_coins.total_score_rank IS '复合分数排名';
COMMENT ON COLUMN dashboard_strong_weak_coins.gain_rank IS '涨跌幅排名';
COMMENT ON COLUMN dashboard_strong_weak_coins.coin_type IS '币种类型（强势币/弱势币/中性币）';

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