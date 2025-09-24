CREATE EXTENSION IF NOT EXISTS http; 
CREATE EXTENSION IF NOT EXISTS pg_cron;


-- 订阅的交易对
CREATE TABLE IF NOT EXISTS market_codes (
    exchange text NOT NULL,        -- 'binance' 或 'okx'
    code text NOT NULL,          -- binance/okx 的 API 使用的交易对形式
    active boolean NOT NULL DEFAULT true,
    PRIMARY KEY (exchange, code)
);

-- 初始化（示例：BTCUSDT, ETHUSDT, BNBUSDT）
INSERT INTO market_codes(exchange, code) VALUES
  ('binance','BTCUSDT'),
  ('binance','ETHUSDT'),
  ('binance','BNBUSDT'),
  ('okx','BTC-USDT'),
  ('okx','ETH-USDT'),
  ('okx','BNB-USDT')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS cron_log (
    id SERIAL PRIMARY KEY,
    job_name TEXT,
    status TEXT,
    message TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);


CREATE TABLE IF NOT EXISTS market_price (
    exchange text NOT NULL,
    symbol text NOT NULL,
    price numeric NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    raw jsonb,
    PRIMARY KEY (exchange, symbol)
);

CREATE TABLE IF NOT EXISTS market_price_history (
    id bigserial PRIMARY KEY,
    exchange text NOT NULL,
    symbol text NOT NULL,
    price numeric NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    raw jsonb
);


-- 分钟级行情
CREATE TABLE IF NOT EXISTS minute_realtime_1 (
    exchange   VARCHAR(20) NOT NULL,   -- 交易所，如 binance, okx
    code       VARCHAR(50) NOT NULL,   -- 交易对，如 BTCUSDT
    datetime   TIMESTAMP NOT NULL,     -- 分钟时间戳
    open       NUMERIC(18,8) NOT NULL,
    high       NUMERIC(18,8) NOT NULL,
    low        NUMERIC(18,8) NOT NULL,
    close      NUMERIC(18,8) NOT NULL,
    volume     NUMERIC(28,8) NOT NULL,
    raw        JSONB,                  -- 原始K线数据
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 小时级行情
CREATE TABLE IF NOT EXISTS hour_realtime_1 (
    exchange   VARCHAR(20) NOT NULL,
    code       VARCHAR(50) NOT NULL,
    datetime   TIMESTAMP NOT NULL,     -- 小时时间戳
    open       NUMERIC(18,8) NOT NULL,
    high       NUMERIC(18,8) NOT NULL,
    low        NUMERIC(18,8) NOT NULL,
    close      NUMERIC(18,8) NOT NULL,
    volume     NUMERIC(28,8) NOT NULL,
    raw        JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 日级行情
CREATE TABLE IF NOT EXISTS day_realtime_1 (
    exchange   VARCHAR(20) NOT NULL,
    code       VARCHAR(50) NOT NULL,
    datetime   DATE NOT NULL,          -- 日期（只存日期，节省空间）
    open       NUMERIC(18,8) NOT NULL,
    high       NUMERIC(18,8) NOT NULL,
    low        NUMERIC(18,8) NOT NULL,
    close      NUMERIC(18,8) NOT NULL,
    volume     NUMERIC(28,8) NOT NULL,
    raw        JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_minute_realtime_1_code_time ON minute_realtime_1 (code, datetime DESC);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_1_code_time ON hour_realtime_1 (code, datetime DESC);
CREATE INDEX IF NOT EXISTS idx_day_realtime_1_code_time ON day_realtime_1 (code, datetime DESC);


-- 分钟行情表
CREATE TABLE IF NOT EXISTS market_price_min (
    id bigserial PRIMARY KEY,
    exchange text NOT NULL,
    symbol text NOT NULL,
    price numeric NOT NULL,
    ts timestamptz NOT NULL,   -- 对齐到分钟
    raw jsonb
);

-- 日行情表
CREATE TABLE IF NOT EXISTS market_price_day (
    id bigserial PRIMARY KEY,
    exchange text NOT NULL,
    symbol text NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric,
    ts date NOT NULL,          -- 对齐到日
    raw jsonb
);

CREATE TABLE cron_job_logs (
    id BIGSERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL,          -- success / error
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);


CREATE OR REPLACE FUNCTION log_cron_job(
    job_name TEXT,
    status TEXT,
    message TEXT,
    start_time TIMESTAMPTZ DEFAULT clock_timestamp()
) RETURNS VOID AS $$
BEGIN
    INSERT INTO cron_job_logs (job_name, status, message, started_at, finished_at)
    VALUES (job_name, status, message, start_time, clock_timestamp());
END;
$$ LANGUAGE plpgsql;


-- 最近 10 条日志
SELECT * FROM cron_job_logs ORDER BY id DESC LIMIT 10;

-- 查看某个任务的错误
SELECT * FROM cron_job_logs WHERE job_name='fetch_minute_prices' AND status='error';
