-- VE（波动率效率）指标数据表创建脚本
-- 该脚本创建存储VE指标计算结果的数据库表结构

-- ============ VE指标表 ============
CREATE TABLE IF NOT EXISTS public.indecator_ve (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,
    datetime TIMESTAMP NOT NULL,
    ve NUMERIC NOT NULL,
    actual_volatility NUMERIC NOT NULL,
    expected_volatility NUMERIC NOT NULL,
    volume_efficiency NUMERIC NOT NULL,
    volatility_efficiency NUMERIC NOT NULL,
    data_points INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 表注释
COMMENT ON TABLE public.indecator_ve IS 'VE（波动率效率）指标数据表';
COMMENT ON COLUMN public.indecator_ve.exchange IS '交易所名称';
COMMENT ON COLUMN public.indecator_ve.symbol IS '交易对符号';
COMMENT ON COLUMN public.indecator_ve.timeframe IS '时间周期（如：1h, 4h, 1d等）';
COMMENT ON COLUMN public.indecator_ve.datetime IS '指标计算时间点';
COMMENT ON COLUMN public.indecator_ve.ve IS 'VE（波动率效率）指标值';
COMMENT ON COLUMN public.indecator_ve.actual_volatility IS '实际波动率（年化）';
COMMENT ON COLUMN public.indecator_ve.expected_volatility IS '预期波动率（年化）';
COMMENT ON COLUMN public.indecator_ve.volume_efficiency IS '成交量效率';
COMMENT ON COLUMN public.indecator_ve.volatility_efficiency IS '波动率效率';
COMMENT ON COLUMN public.indecator_ve.data_points IS '用于计算的数据点数量';

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_indecator_ve_exchange_symbol 
    ON public.indecator_ve(exchange, symbol);
    
CREATE INDEX IF NOT EXISTS idx_indecator_ve_datetime 
    ON public.indecator_ve(datetime DESC);
    
CREATE INDEX IF NOT EXISTS idx_indecator_ve_timeframe 
    ON public.indecator_ve(timeframe);
    
CREATE INDEX IF NOT EXISTS idx_indecator_ve_exchange_symbol_timeframe_datetime 
    ON public.indecator_ve(exchange, symbol, timeframe, datetime DESC);

-- 创建唯一约束，防止重复数据
CREATE UNIQUE INDEX IF NOT EXISTS uq_indecator_ve_exchange_symbol_timeframe_datetime 
    ON public.indecator_ve(exchange, symbol, timeframe, datetime);

-- 创建触发器函数，自动更新updated_at字段
CREATE OR REPLACE FUNCTION update_ve_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
DROP TRIGGER IF EXISTS trigger_update_ve_updated_at ON public.indecator_ve;
CREATE TRIGGER trigger_update_ve_updated_at
    BEFORE UPDATE ON public.indecator_ve
    FOR EACH ROW
    EXECUTE FUNCTION update_ve_updated_at();

-- ============ VE指标批量计算任务表 ============
-- 用于记录VE指标批量计算任务的状态
CREATE TABLE IF NOT EXISTS public.indecator_ve_batch_jobs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR NOT NULL,
    exchange VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,
    symbols_count INTEGER NOT NULL,
    processed_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    status VARCHAR NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.indecator_ve_batch_jobs IS 'VE指标批量计算任务记录表';
COMMENT ON COLUMN public.indecator_ve_batch_jobs.job_name IS '任务名称';
COMMENT ON COLUMN public.indecator_ve_batch_jobs.exchange IS '交易所名称';
COMMENT ON COLUMN public.indecator_ve_batch_jobs.timeframe IS '时间周期';
COMMENT ON COLUMN public.indecator_ve_batch_jobs.symbols_count IS '总交易对数量';
COMMENT ON COLUMN public.indecator_ve_batch_jobs.processed_count IS '已处理交易对数量';
COMMENT ON COLUMN public.indecator_ve_batch_jobs.success_count IS '成功计算数量';
COMMENT ON COLUMN public.indecator_ve_batch_jobs.failed_count IS '失败计算数量';
COMMENT ON COLUMN public.indecator_ve_batch_jobs.status IS '任务状态';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_indecator_ve_batch_jobs_status 
    ON public.indecator_ve_batch_jobs(status);
    
CREATE INDEX IF NOT EXISTS idx_indecator_ve_batch_jobs_exchange_timeframe 
    ON public.indecator_ve_batch_jobs(exchange, timeframe);

-- 创建触发器
DROP TRIGGER IF EXISTS trigger_update_ve_batch_jobs_updated_at ON public.indecator_ve_batch_jobs;
CREATE TRIGGER trigger_update_ve_batch_jobs_updated_at
    BEFORE UPDATE ON public.indecator_ve_batch_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_ve_updated_at();

-- ============ 数据插入示例 ============
-- INSERT INTO public.indecator_ve (
--     exchange, symbol, timeframe, datetime, ve, 
--     actual_volatility, expected_volatility, 
--     volume_efficiency, volatility_efficiency, data_points
-- ) VALUES (
--     'binance', 'BTCUSDT', '1h', NOW(), 1.072,
--     0.025, 0.023, 1.15, 0.93, 720
-- );

-- ============ 常用查询示例 ============
-- 获取最新VE指标数据
-- SELECT * FROM public.indecator_ve 
-- WHERE exchange = 'binance' AND symbol = 'BTCUSDT' AND timeframe = '1h'
-- ORDER BY datetime DESC LIMIT 1;

-- 获取多个交易对的最新VE指标
-- SELECT symbol, ve, actual_volatility, volume_efficiency, datetime
-- FROM public.indecator_ve 
-- WHERE exchange = 'binance' AND timeframe = '1h' 
--     AND datetime >= NOW() - INTERVAL '1 hour'
-- ORDER BY ve DESC;

-- 获取VE指标历史趋势
-- SELECT datetime, ve, actual_volatility, volume_efficiency
-- FROM public.indecator_ve 
-- WHERE exchange = 'binance' AND symbol = 'BTCUSDT' AND timeframe = '1h'
--     AND datetime >= NOW() - INTERVAL '7 days'
-- ORDER BY datetime ASC;