# 表结构修改指南：调整 tuning_tasks 和 tuning_results 主键

## 修改内容概述

本指南描述了如何修改数据库表结构，将：
- `tuning_tasks` 表：去掉 id 自增主键，将 `task_id` 设为主键（字符串类型UUID）
- `tuning_results` 表：去掉 id 自增主键，将 `run_id` 和 `task_id` 设为联合主键

## 前提条件

在执行修改前，请确保：
1. **备份数据库**：完整备份所有数据，特别是 `tuning_tasks` 和 `tuning_results` 表
2. **停止相关服务**：关闭所有可能访问这些表的应用程序和服务
3. **检查空间**：确保数据库有足够的空间执行操作

## 执行步骤

1. **连接到数据库**：
   ```bash
   psql -U <username> -d <database_name>
   ```

2. **执行SQL脚本**：
   ```sql
   \i /Users/aaronkliu/Documents/project/cfsQuant/backend/update_tables_primary_keys.sql
   ```

3. **验证修改**：
   ```sql
   -- 验证 tuning_tasks 表结构
   \d tuning_tasks
   
   -- 验证 tuning_results 表结构
   \d tuning_results
   
   -- 验证数据是否正确恢复
   SELECT COUNT(*) FROM tuning_tasks;
   SELECT COUNT(*) FROM tuning_results;
   ```

## 重要说明

### 数据类型兼容性

- 修改后，`task_id` 字段使用 `VARCHAR(36)` 类型存储UUID字符串，与代码中的 `str(uuid.uuid4())` 保持一致
- 这种修改不会影响现有代码逻辑，因为代码始终以字符串形式处理UUID

### 数据恢复策略

提供的SQL脚本中的数据恢复部分是**简化版本**，主要用于演示。在实际生产环境中：

1. 如果需要保留原有数据的关联关系，建议在执行脚本前进行更详细的数据分析
2. 脚本中通过生成新的UUID来填充 `task_id` 字段，这意味着原有数据的ID关联会丢失
3. 对于 `tuning_results` 表，脚本简单地将所有记录关联到同一条 `tuning_tasks` 记录，这仅适用于演示

### 应用程序影响

- 现有代码与新的表结构完全兼容，无需修改代码
- `tuning_service.py` 文件中使用的所有数据库操作都与字符串类型的UUID兼容
- 所有SQL查询中的条件语句仍然有效

## 回滚方案

如果修改后出现问题，可以使用以下步骤回滚：

1. **删除新表**：
   ```sql
   DROP TABLE IF EXISTS tuning_tasks;
   DROP TABLE IF EXISTS tuning_results;
   ```

2. **恢复原始表**：
   ```sql
   ALTER TABLE tuning_tasks_backup RENAME TO tuning_tasks;
   ALTER TABLE tuning_results_backup RENAME TO tuning_results;
   ```

3. **重建索引和约束**：
   ```sql
   CREATE INDEX idx_tuning_results_task ON public.tuning_results USING btree (task_id);
   CREATE INDEX idx_tuning_tasks_status ON public.tuning_tasks USING btree (status);
   ```

## 后续验证

修改完成后，启动应用程序并验证以下功能：

1. 创建新的tuning任务
2. 查看任务状态
3. 验证任务完成后的数据更新
4. 检查所有相关API端点的响应

## 注意事项

- 此修改涉及表结构变更，请在低峰时段执行
- 执行前务必完成数据备份
- 在生产环境中，建议先在测试环境验证
- 如有疑问，请联系数据库管理员或开发团队