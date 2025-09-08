-- 为分钟级行情数据表添加复合索引，优化查询性能
-- 注意：如果表已经存在但没有索引，运行此脚本

-- 为minute_realtime表添加(code, datetime)复合索引
-- 这是最常用的查询条件：WHERE code = :code AND datetime BETWEEN :start AND :end
CREATE INDEX IF NOT EXISTS idx_minute_realtime_code_time 
ON public.minute_realtime (code, datetime);

-- 为day_realtime表添加(code, datetime)复合索引
CREATE INDEX IF NOT EXISTS idx_day_realtime_code_time 
ON public.day_realtime (code, datetime);

-- 为分钟级行情数据表添加仅datetime的索引，优化按时间范围的查询
CREATE INDEX IF NOT EXISTS idx_minute_realtime_datetime 
ON public.minute_realtime (datetime);

-- 为日级行情数据表添加仅datetime的索引
CREATE INDEX IF NOT EXISTS idx_day_realtime_datetime 
ON public.day_realtime (datetime);

-- 分析表以更新统计信息，帮助查询优化器做出更好的决策
ANALYZE public.minute_realtime;
ANALYZE public.day_realtime;

-- 如果数据库支持，可以考虑添加覆盖索引，避免回表操作
-- 这将包含查询中常用的所有列
-- CREATE INDEX IF NOT EXISTS idx_minute_realtime_covering 
-- ON public.minute_realtime (code, datetime) INCLUDE (open, high, low, close, volume);

-- 为其他可能使用的表也添加必要的索引
CREATE INDEX IF NOT EXISTS idx_runs_strategy 
ON public.runs (strategy);

CREATE INDEX IF NOT EXISTS idx_runs_code 
ON public.runs (code);