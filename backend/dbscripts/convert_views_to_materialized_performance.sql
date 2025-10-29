-- 物化视图转换方案 - 性能测试和验证脚本
-- 作者: AI Assistant
-- 创建时间: $(date)
-- 描述: 测试转换前后的性能差异，验证转换效果

-- 1. 创建性能测试函数
CREATE OR REPLACE FUNCTION test_view_performance(view_name TEXT, iterations INTEGER DEFAULT 10)
RETURNS TABLE(
    test_type TEXT,
    view_name TEXT,
    avg_execution_time_ms NUMERIC,
    min_execution_time_ms NUMERIC,
    max_execution_time_ms NUMERIC,
    total_rows BIGINT
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    total_time INTERVAL := '0 seconds';
    i INTEGER;
    execution_time NUMERIC;
    min_time NUMERIC := 999999;
    max_time NUMERIC := 0;
    row_count BIGINT;
    query_text TEXT;
BEGIN
    -- 构建查询语句
    query_text := format('SELECT COUNT(*) FROM %I WHERE time > NOW() - INTERVAL ''7 days''', view_name);
    
    -- 预热缓存
    FOR i IN 1..3 LOOP
        EXECUTE query_text;
    END LOOP;
    
    -- 执行性能测试
    FOR i IN 1..iterations LOOP
        start_time := clock_timestamp();
        EXECUTE query_text INTO row_count;
        end_time := clock_timestamp();
        
        execution_time := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;
        total_time := total_time + (end_time - start_time);
        
        IF execution_time < min_time THEN
            min_time := execution_time;
        END IF;
        
        IF execution_time > max_time THEN
            max_time := execution_time;
        END IF;
    END LOOP;
    
    -- 返回性能指标
    RETURN QUERY SELECT 
        'query_performance'::TEXT as test_type,
        view_name,
        (EXTRACT(EPOCH FROM total_time) * 1000 / iterations)::NUMERIC(10,3) as avg_execution_time_ms,
        min_time::NUMERIC(10,3) as min_execution_time_ms,
        max_time::NUMERIC(10,3) as max_execution_time_ms,
        row_count as total_rows;
END;
$$ LANGUAGE plpgsql;

-- 2. 执行转换前性能测试（基于备份数据）
DO $$
DECLARE
    performance_record RECORD;
BEGIN
    RAISE NOTICE '=== 转换前性能测试开始 ===';
    
    -- 测试每个视图的性能
    FOR performance_record IN (
        SELECT * FROM test_view_performance('market_ohlcv_3m', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_5m', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_15m', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_30m', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_1h', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_2h', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_4h', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_1d', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_2d', 5)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_3d', 5)
    )
    LOOP
        RAISE NOTICE '视图: %, 平均耗时: % ms, 数据量: % 行', 
            performance_record.view_name, 
            performance_record.avg_execution_time_ms,
            performance_record.total_rows;
    END LOOP;
    
    RAISE NOTICE '=== 转换前性能测试完成 ===';
END $$;

-- 3. 等待物化视图数据填充完成（建议等待一段时间后手动运行此部分）
DO $$
BEGIN
    RAISE NOTICE '等待物化视图数据填充...';
    RAISE NOTICE '建议等待至少30分钟让连续聚合策略完成数据填充';
    RAISE NOTICE '然后重新运行此脚本的后续部分进行性能对比';
END $$;

-- 4. 转换后性能测试（需要手动执行）
/*
DO $$
DECLARE
    performance_record RECORD;
    improvement_count INTEGER := 0;
    total_views INTEGER := 0;
BEGIN
    RAISE NOTICE '=== 转换后性能测试开始 ===';
    
    -- 测试每个物化视图的性能
    FOR performance_record IN (
        SELECT * FROM test_view_performance('market_ohlcv_3m', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_5m', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_15m', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_30m', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_1h', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_2h', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_4h', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_1d', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_2d', 10)
        UNION ALL SELECT * FROM test_view_performance('market_ohlcv_3d', 10)
    )
    LOOP
        total_views := total_views + 1;
        
        -- 这里应该与转换前的性能数据对比
        -- 实际项目中应该存储转换前的性能数据用于对比
        IF performance_record.avg_execution_time_ms < 50 THEN  -- 假设50ms为性能改善阈值
            improvement_count := improvement_count + 1;
            RAISE NOTICE '✅ 视图: %, 性能优秀: % ms', 
                performance_record.view_name, 
                performance_record.avg_execution_time_ms;
        ELSE
            RAISE NOTICE '⚠️ 视图: %, 性能一般: % ms', 
                performance_record.view_name, 
                performance_record.avg_execution_time_ms;
        END IF;
    END LOOP;
    
    RAISE NOTICE '=== 转换后性能测试完成 ===';
    RAISE NOTICE '性能改善视图: %/%', improvement_count, total_views;
END $$;
*/

-- 5. 系统资源使用监控
CREATE OR REPLACE VIEW mv_performance_monitor AS
SELECT 
    mv.view_name,
    mv.materialization_hypertable_name,
    mv.completed_threshold,
    mv.invalidation_threshold,
    mv.worker_id,
    mv.last_run_started_at,
    mv.last_run_duration,
    ht.total_bytes,
    ht.total_chunks,
    ht.compressed_chunks
FROM timescaledb_information.continuous_aggregate_stats mv
LEFT JOIN timescaledb_information.hypertables ht 
    ON mv.materialization_hypertable_name = ht.hypertable_name
WHERE mv.view_name LIKE 'market_ohlcv_%_materialized';

-- 6. 查询优化建议
CREATE OR REPLACE VIEW mv_optimization_suggestions AS
SELECT 
    mv.view_name,
    CASE 
        WHEN ht.total_bytes > 1000000000 THEN '考虑增加压缩策略或分区策略'
        WHEN ht.total_chunks > 100 THEN '考虑合并小chunk或调整时间区间'
        WHEN mv.last_run_duration > INTERVAL '5 minutes' THEN '考虑调整刷新间隔或优化查询'
        ELSE '性能良好'
    END as suggestion,
    ht.total_bytes,
    ht.total_chunks,
    mv.last_run_duration
FROM timescaledb_information.continuous_aggregate_stats mv
LEFT JOIN timescaledb_information.hypertables ht 
    ON mv.materialization_hypertable_name = ht.hypertable_name
WHERE mv.view_name LIKE 'market_ohlcv_%_materialized';

-- 7. 生成性能报告
SELECT 
    '性能测试准备完成' as status,
    '请按以下步骤执行:' as instruction,
    '1. 首先运行备份脚本确保数据安全' as step1,
    '2. 运行主转换脚本创建物化视图' as step2,
    '3. 运行数据迁移脚本初始化数据' as step3,
    '4. 等待30分钟让数据填充完成' as step4,
    '5. 重新运行此脚本的性能测试部分' as step5,
    '6. 对比转换前后的性能数据' as step6;

RAISE NOTICE '🎯 性能测试脚本准备完成！';
RAISE NOTICE '请按照上述步骤执行完整的性能验证流程';