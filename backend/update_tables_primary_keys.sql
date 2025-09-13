-- 修改 tuning_tasks 和 tuning_results 表主键结构的SQL脚本
-- 1. 先备份现有数据
-- 2. 删除现有表
-- 3. 创建新结构表
-- 4. 恢复数据

-- 停止后端服务避免数据写入冲突
-- 注意：执行前请确保已停止所有可能访问这些表的服务

-- ===== 备份数据 =====

-- 备份 tuning_tasks 表数据
CREATE TABLE IF NOT EXISTS tuning_tasks_backup AS SELECT * FROM tuning_tasks;
-- 备份 tuning_results 表数据
CREATE TABLE IF NOT EXISTS tuning_results_backup AS SELECT * FROM tuning_results;

-- ===== 删除现有表和序列 =====

-- 删除依赖关系
ALTER TABLE tuning_results DROP CONSTRAINT IF EXISTS tuning_results_task_id_fkey;

-- 删除索引
DROP INDEX IF EXISTS idx_tuning_results_task;
DROP INDEX IF EXISTS idx_tuning_tasks_status;

-- 删除表
DROP TABLE IF EXISTS tuning_results;
DROP TABLE IF EXISTS tuning_tasks;

-- 删除序列
DROP SEQUENCE IF EXISTS tuning_tasks_id_seq;
DROP SEQUENCE IF EXISTS tuning_results_id_seq;

-- ===== 创建新结构表 =====

-- 创建 tuning_tasks 表（使用 task_id 作为主键）
CREATE TABLE public.tuning_tasks (
    task_id VARCHAR(36) NOT NULL,  -- 字符串类型UUID，与代码中使用的str(uuid.uuid4())保持一致
    strategy text,          -- 策略名称
    status text,            -- 任务状态
    total int4,             -- 总运行次数
    finished int4,          -- 已完成次数
    created_at timestamp DEFAULT now(),  -- 创建时间
    PRIMARY KEY (task_id)   -- 设置 task_id 为主键
);

-- 创建 tuning_results 表（使用 run_id 和 task_id 作为联合主键）
CREATE TABLE public.tuning_results (
    task_id VARCHAR(36) NOT NULL,  -- 字符串类型UUID，与 tuning_tasks.task_id 匹配
    run_id varchar NOT NULL,-- 回测运行ID
    params jsonb,           -- 参数配置（JSONB格式）
    created_at timestamp DEFAULT now(),  -- 创建时间
    PRIMARY KEY (run_id, task_id)  -- 设置联合主键
);

-- ===== 恢复数据 =====

-- 恢复 tuning_tasks 数据
-- 注意：由于原有数据没有task_id，这里生成新的UUID字符串
-- 实际生产环境请根据具体业务需求调整数据恢复策略
INSERT INTO tuning_tasks (task_id, strategy, status, total, finished, created_at)
SELECT 
    -- 生成UUID字符串格式（与Python代码中的str(uuid.uuid4())保持一致）
    lower(regexp_replace(CAST(md5(random()::text || clock_timestamp()::text) AS varchar), '^(....)(....)(....)(....)(....)$', '\1-\2-\3-\4-\5')) AS task_id,
    strategy, 
    status, 
    total, 
    finished, 
    created_at 
FROM tuning_tasks_backup;

-- 恢复 tuning_results 数据，需要匹配新的task_id
-- 注意：这里是一个简化的示例，实际应用中需要根据业务逻辑正确关联数据
-- 由于原始数据中没有关联信息，这里只是为了演示目的
-- 在实际生产环境中，建议在修改表结构前确保有正确的关联关系
INSERT INTO tuning_results (task_id, run_id, params, created_at)
SELECT 
    (SELECT task_id FROM tuning_tasks LIMIT 1) AS task_id, -- 仅用于演示，实际需要正确关联
    run_id, 
    params, 
    created_at 
FROM tuning_results_backup;

-- 重要提示：
-- 1. 上述数据恢复是简化版本，实际使用时需要根据业务需求调整
-- 2. 建议在执行前备份所有相关数据
-- 3. 执行后需要验证应用程序功能是否正常

-- ===== 重建索引和约束 =====

-- 重建索引
CREATE INDEX idx_tuning_results_task ON public.tuning_results USING btree (task_id);
CREATE INDEX idx_tuning_tasks_status ON public.tuning_tasks USING btree (status);

-- 重建外键约束
ALTER TABLE public.tuning_results ADD FOREIGN KEY (task_id) 
REFERENCES tuning_tasks(task_id) ON DELETE CASCADE;
ALTER TABLE public.tuning_results ADD FOREIGN KEY (run_id) 
REFERENCES runs(run_id) ON DELETE CASCADE;

-- ===== 清理备份表（可选）=====
-- DROP TABLE IF EXISTS tuning_tasks_backup;
-- DROP TABLE IF EXISTS tuning_results_backup;

-- 脚本执行完成后，请验证数据完整性和应用程序功能
-- 注意：此脚本会修改表结构，请在执行前确保已做好数据备份！