-- 物化视图转换方案 - 数据备份和验证脚本
-- 作者: AI Assistant
-- 创建时间: $(date)
-- 描述: 将market_ohlcv_*普通视图转换为物化视图的备份和验证脚本

-- 1. 创建备份表，存储当前视图定义和数据快照
DO $$
BEGIN
    -- 检查备份表是否存在，不存在则创建
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'backup_view_definitions') THEN
        CREATE TABLE backup_view_definitions (
            id SERIAL PRIMARY KEY,
            view_name VARCHAR(100) NOT NULL,
            view_definition TEXT NOT NULL,
            backup_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            row_count BIGINT,
            status VARCHAR(50) DEFAULT 'created'
        );
        
        RAISE NOTICE '备份表 backup_view_definitions 创建成功';
    END IF;
END $$;

-- 2. 备份当前视图定义
INSERT INTO backup_view_definitions (view_name, view_definition, row_count)
SELECT 
    table_name as view_name,
    view_definition,
    (SELECT COUNT(*) FROM information_schema.tables WHERE table_name = table_name) as row_count
FROM information_schema.views 
WHERE table_name LIKE 'market_ohlcv_%'
AND table_schema = 'public';

-- 3. 验证备份数据
DO $$
DECLARE
    backup_count INTEGER;
    view_count INTEGER;
BEGIN
    -- 统计备份的视图数量
    SELECT COUNT(*) INTO backup_count FROM backup_view_definitions 
    WHERE view_name LIKE 'market_ohlcv_%';
    
    -- 统计实际存在的视图数量
    SELECT COUNT(*) INTO view_count FROM information_schema.views 
    WHERE table_name LIKE 'market_ohlcv_%' AND table_schema = 'public';
    
    IF backup_count = view_count AND backup_count = 10 THEN
        RAISE NOTICE '✅ 所有10个视图定义备份成功，备份数量: %', backup_count;
    ELSE
        RAISE WARNING '⚠️ 视图备份数量不匹配，备份: %, 实际: %', backup_count, view_count;
    END IF;
END $$;

-- 4. 创建数据样本备份表
DO $$
BEGIN
    -- 为每个视图创建数据样本备份表
    FOR i IN 1..10 LOOP
        EXECUTE format('CREATE TABLE IF NOT EXISTS backup_data_sample_%s AS SELECT * FROM market_ohlcv_%sm LIMIT 1000', 
                       CASE i
                           WHEN 1 THEN '3m' WHEN 2 THEN '5m' WHEN 3 THEN '15m' WHEN 4 THEN '30m'
                           WHEN 5 THEN '1h' WHEN 6 THEN '2h' WHEN 7 THEN '4h' WHEN 8 THEN '1d'
                           WHEN 9 THEN '2d' WHEN 10 THEN '3d'
                       END,
                       CASE i
                           WHEN 1 THEN '3' WHEN 2 THEN '5' WHEN 3 THEN '15' WHEN 4 THEN '30'
                           WHEN 5 THEN '1' WHEN 6 THEN '2' WHEN 7 THEN '4' WHEN 8 THEN '1'
                           WHEN 9 THEN '2' WHEN 10 THEN '3'
                       END);
    END LOOP;
    
    RAISE NOTICE '✅ 数据样本备份表创建完成';
END $$;

-- 5. 验证当前视图数据完整性
DO $$
DECLARE
    view_name TEXT;
    row_count BIGINT;
    total_views INTEGER := 0;
    valid_views INTEGER := 0;
BEGIN
    -- 检查每个视图的数据完整性
    FOR view_name IN (SELECT table_name FROM information_schema.views 
                      WHERE table_name LIKE 'market_ohlcv_%' AND table_schema = 'public') 
    LOOP
        total_views := total_views + 1;
        
        -- 尝试查询视图数据
        BEGIN
            EXECUTE format('SELECT COUNT(*) FROM %I', view_name) INTO row_count;
            
            IF row_count > 0 THEN
                valid_views := valid_views + 1;
                RAISE NOTICE '✅ 视图 % 数据验证通过，行数: %', view_name, row_count;
            ELSE
                RAISE WARNING '⚠️ 视图 % 数据为空', view_name;
            END IF;
            
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING '❌ 视图 % 查询失败: %', view_name, SQLERRM;
        END;
    END LOOP;
    
    RAISE NOTICE '数据验证完成: 有效视图 %/%', valid_views, total_views;
END $$;

-- 6. 记录备份完成状态
UPDATE backup_view_definitions 
SET status = 'backup_completed', row_count = (
    SELECT COUNT(*) FROM information_schema.tables 
    WHERE table_name = view_name
)
WHERE view_name LIKE 'market_ohlcv_%';

RAISE NOTICE '🎉 数据备份和验证脚本执行完成！';
RAISE NOTICE '下一步: 运行转换脚本将视图转换为物化视图';