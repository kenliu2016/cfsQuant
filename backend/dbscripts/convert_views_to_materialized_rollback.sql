-- 物化视图转换方案 - 回滚脚本
-- 作者: AI Assistant
-- 创建时间: $(date)
-- 描述: 在转换失败时恢复原始视图和数据

-- 0. 设置事务和错误处理
BEGIN;

-- 1. 检查当前状态
DO $$
DECLARE
    backup_count INTEGER;
    mv_count INTEGER;
    view_count INTEGER;
BEGIN
    -- 检查备份数据
    SELECT COUNT(*) INTO backup_count FROM backup_view_definitions 
    WHERE view_name LIKE 'market_ohlcv_%' AND status = 'backup_completed';
    
    -- 检查物化视图数量
    SELECT COUNT(*) INTO mv_count FROM timescaledb_information.continuous_aggregates 
    WHERE view_name LIKE 'market_ohlcv_%_materialized';
    
    -- 检查当前视图数量
    SELECT COUNT(*) INTO view_count FROM information_schema.views 
    WHERE table_name LIKE 'market_ohlcv_%' AND table_schema = 'public';
    
    RAISE NOTICE '当前状态: 备份视图 %, 物化视图 %, 当前视图 %', 
        backup_count, mv_count, view_count;
        
    IF backup_count = 10 THEN
        RAISE NOTICE '✅ 备份数据完整，可以执行回滚';
    ELSE
        RAISE WARNING '⚠️ 备份数据不完整，回滚可能无法完全恢复';
    END IF;
END $$;

-- 2. 恢复原始视图定义
DO $$
DECLARE
    view_record RECORD;
    restored_count INTEGER := 0;
BEGIN
    -- 从备份表中恢复视图定义
    FOR view_record IN (SELECT view_name, view_definition FROM backup_view_definitions 
                        WHERE view_name LIKE 'market_ohlcv_%' AND status = 'backup_completed') 
    LOOP
        BEGIN
            -- 删除当前视图（如果存在）
            EXECUTE format('DROP VIEW IF EXISTS %I CASCADE', view_record.view_name);
            
            -- 恢复原始视图定义
            EXECUTE view_record.view_definition;
            
            restored_count := restored_count + 1;
            RAISE NOTICE '✅ 视图 % 恢复成功', view_record.view_name;
            
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING '❌ 视图 % 恢复失败: %', view_record.view_name, SQLERRM;
        END;
    END LOOP;
    
    RAISE NOTICE '视图恢复完成: %/%', restored_count, 10;
END $$;

-- 3. 清理物化视图和相关对象
DO $$
DECLARE
    mv_name TEXT;
    removed_count INTEGER := 0;
BEGIN
    -- 删除所有相关的物化视图
    FOR mv_name IN (SELECT view_name FROM timescaledb_information.continuous_aggregates 
                    WHERE view_name LIKE 'market_ohlcv_%_materialized') 
    LOOP
        BEGIN
            -- 删除连续聚合策略
            PERFORM remove_continuous_aggregate_policy(mv_name, if_exists => true);
            
            -- 删除物化视图
            EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS %I CASCADE', mv_name);
            
            removed_count := removed_count + 1;
            RAISE NOTICE '✅ 物化视图 % 删除成功', mv_name;
            
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING '❌ 物化视图 % 删除失败: %', mv_name, SQLERRM;
        END;
    END LOOP;
    
    RAISE NOTICE '物化视图清理完成: % 个对象已删除', removed_count;
END $$;

-- 4. 清理临时表
DROP TABLE IF EXISTS backup_data_sample_3m;
DROP TABLE IF EXISTS backup_data_sample_5m;
DROP TABLE IF EXISTS backup_data_sample_15m;
DROP TABLE IF EXISTS backup_data_sample_30m;
DROP TABLE IF EXISTS backup_data_sample_1h;
DROP TABLE IF EXISTS backup_data_sample_2h;
DROP TABLE IF EXISTS backup_data_sample_4h;
DROP TABLE IF EXISTS backup_data_sample_1d;
DROP TABLE IF EXISTS backup_data_sample_2d;
DROP TABLE IF EXISTS backup_data_sample_3d;

RAISE NOTICE '✅ 临时数据样本表清理完成';

-- 5. 验证回滚结果
DO $$
DECLARE
    view_count INTEGER;
    mv_count INTEGER;
    data_consistent BOOLEAN := true;
BEGIN
    -- 检查视图数量
    SELECT COUNT(*) INTO view_count FROM information_schema.views 
    WHERE table_name LIKE 'market_ohlcv_%' AND table_schema = 'public';
    
    -- 检查物化视图数量
    SELECT COUNT(*) INTO mv_count FROM timescaledb_information.continuous_aggregates 
    WHERE view_name LIKE 'market_ohlcv_%_materialized';
    
    -- 验证数据一致性
    FOR i IN 1..10 LOOP
        DECLARE
            view_name TEXT := CASE i
                WHEN 1 THEN 'market_ohlcv_3m' WHEN 2 THEN 'market_ohlcv_5m' WHEN 3 THEN 'market_ohlcv_15m' WHEN 4 THEN 'market_ohlcv_30m'
                WHEN 5 THEN 'market_ohlcv_1h' WHEN 6 THEN 'market_ohlcv_2h' WHEN 7 THEN 'market_ohlcv_4h' WHEN 8 THEN 'market_ohlcv_1d'
                WHEN 9 THEN 'market_ohlcv_2d' WHEN 10 THEN 'market_ohlcv_3d'
            END;
            old_count BIGINT;
            new_count BIGINT;
        BEGIN
            -- 检查备份数据量
            SELECT COUNT(*) INTO old_count FROM backup_view_definitions 
            WHERE view_name = view_name;
            
            -- 检查当前数据量
            EXECUTE format('SELECT COUNT(*) FROM %I', view_name) INTO new_count;
            
            IF old_count != new_count THEN
                data_consistent := false;
                RAISE WARNING '⚠️ 视图 % 数据不一致', view_name;
            END IF;
        END;
    END LOOP;
    
    IF view_count = 10 AND mv_count = 0 AND data_consistent THEN
        RAISE NOTICE '🎉 回滚成功！系统已恢复到转换前状态';
        RAISE NOTICE '视图数量: %, 物化视图数量: %, 数据一致性: %', view_count, mv_count, data_consistent;
    ELSE
        RAISE WARNING '⚠️ 回滚结果不完整，请手动检查';
        RAISE NOTICE '视图数量: %, 物化视图数量: %, 数据一致性: %', view_count, mv_count, data_consistent;
    END IF;
END $$;

-- 6. 更新备份状态
UPDATE backup_view_definitions 
SET status = 'rollback_completed'
WHERE view_name LIKE 'market_ohlcv_%';

COMMIT;

RAISE NOTICE '🔙 回滚脚本执行完成！';
RAISE NOTICE '系统已恢复到物化视图转换前的状态';