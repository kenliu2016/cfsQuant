# 后端数据查询性能优化指南

本文档详细说明了已实现的性能优化措施以及其他可进一步优化的方向，旨在提升分时行情接口和其他数据查询的响应速度。

## 已实现的优化

### 1. 数据库索引优化

已创建 `optimize_performance.sql` 文件，包含以下索引优化建议：

- 为 `minute_realtime` 表添加 `(code, datetime)` 复合索引，这是查询中最常用的过滤条件组合
- 为 `day_realtime` 表添加 `(code, datetime)` 复合索引
- 为 `minute_realtime` 和 `day_realtime` 表添加 `datetime` 单列索引，支持仅按时间范围查询的场景
- 添加 `ANALYZE` 语句以更新表统计信息，帮助查询优化器做出更好的执行计划

执行方式：
```bash
psql -U cfs -d quant -h localhost -p 5432 -f backend/db/optimize_performance.sql
```

### 2. 缓存机制实现

已创建 `cache_service.py` 文件，实现了基于 Redis 的缓存服务：

- 使用 `cache_dataframe_result` 装饰器简化数据缓存逻辑
- 支持自动序列化和反序列化 DataFrame 对象
- 提供灵活的过期时间设置（5分钟默认缓存，24小时长期缓存）
- 实现了缓存键命名规范，方便管理和清理
- 提供清除特定代码或全部缓存的功能

### 3. 服务层缓存应用

已修改 `market_service.py` 文件，为所有数据查询函数添加缓存支持：

- `get_candles`：使用5分钟缓存（适用于高频查询的实时数据）
- `get_predictions`：使用24小时缓存（适用于不频繁变动的预测数据）
- `get_daily_candles`：使用5分钟缓存（适用于日线数据）
- `get_intraday`：使用5分钟缓存（适用于分时数据）
- 新增 `refresh_market_data_cache` 函数，用于手动刷新缓存

## 其他可优化方向

### 1. 数据库连接池优化

当前 `db.py` 中的连接池配置为：
```python
pool_pre_ping=True,  # Ensures connections are alive
pool_size=5,         # Number of persistent connections
max_overflow=10      # Maximum number of temporary connections
```

可根据实际负载调整这些参数：

- **高并发场景**：增加 `pool_size` 和 `max_overflow` 值
- **资源受限环境**：适当减小这些值以减少数据库连接开销

### 2. 查询性能优化

- **分页查询**：对于大数据量查询，实现分页机制，避免一次性返回过多数据
- **查询字段优化**：只选择必要的字段，避免 `SELECT *` 查询
- **时间范围限制**：在接口层面增加时间范围限制，防止查询过大的数据量

### 3. 异步处理

- 将同步数据库查询改为异步模式，提高并发处理能力
- 使用 FastAPI 的异步特性，优化请求处理流程

### 4. 监控与日志

- 添加性能监控，记录查询执行时间和缓存命中率
- 实现慢查询日志，便于发现性能瓶颈

### 5. 硬件与基础设施优化

- 考虑使用更高性能的数据库服务器或云实例
- 配置数据库服务器的内存和存储参数

## 实施建议

1. 首先执行数据库索引优化脚本，这通常能带来最显著的性能提升
2. 确保 Redis 服务已启动并可被应用访问
3. 监控缓存命中率，根据实际情况调整缓存过期时间
4. 在数据更新后，调用 `refresh_market_data_cache` 函数刷新相关缓存
5. 根据系统负载和性能表现，逐步实施其他优化措施

## 测试方法

使用提供的 `test_intraday_response_time.js` 脚本测试优化效果：

```bash
node test_intraday_response_time.js
```

记录优化前后的响应时间对比，评估优化效果。