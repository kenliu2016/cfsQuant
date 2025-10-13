-- 表: market_codes
CREATE TABLE IF NOT EXISTS public.market_codes (
    exchange text NOT NULL,
    code text NOT NULL,
    active bool NOT NULL DEFAULT true,
    excode text NOT NULL,
    watch bool NOT NULL DEFAULT false,
    PRIMARY KEY (exchange, code)
);

DROP TABLE IF EXISTS public.minute_realtime CASCADE;

CREATE TABLE public.minute_realtime (
    exchange VARCHAR NOT NULL,
    code VARCHAR NOT NULL,
    datetime TIMESTAMP NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    raw JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
) PARTITION BY RANGE (datetime);

DROP TABLE IF EXISTS public.hour_realtime CASCADE;

CREATE TABLE public.hour_realtime (
    exchange VARCHAR NOT NULL,
    code VARCHAR NOT NULL,
    datetime TIMESTAMP NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    raw JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
) PARTITION BY RANGE (datetime);

DROP TABLE IF EXISTS public.day_realtime CASCADE;

CREATE TABLE public.day_realtime (
    exchange VARCHAR NOT NULL,
    code VARCHAR NOT NULL,
    datetime DATE NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    raw JSONB,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
) PARTITION BY RANGE (datetime);

-- 分钟级K线表
CREATE TABLE IF NOT EXISTS minute_realtime_2022_09 PARTITION OF minute_realtime FOR VALUES FROM ('2022-09-01') TO ('2022-10-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2022_10 PARTITION OF minute_realtime FOR VALUES FROM ('2022-10-01') TO ('2022-11-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2022_11 PARTITION OF minute_realtime FOR VALUES FROM ('2022-11-01') TO ('2022-12-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2022_12 PARTITION OF minute_realtime FOR VALUES FROM ('2022-12-01') TO ('2023-01-01');
-- 2023年分钟级分区
CREATE TABLE IF NOT EXISTS minute_realtime_2023_01 PARTITION OF minute_realtime FOR VALUES FROM ('2023-01-01') TO ('2023-02-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_02 PARTITION OF minute_realtime FOR VALUES FROM ('2023-02-01') TO ('2023-03-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_03 PARTITION OF minute_realtime FOR VALUES FROM ('2023-03-01') TO ('2023-04-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_04 PARTITION OF minute_realtime FOR VALUES FROM ('2023-04-01') TO ('2023-05-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_05 PARTITION OF minute_realtime FOR VALUES FROM ('2023-05-01') TO ('2023-06-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_06 PARTITION OF minute_realtime FOR VALUES FROM ('2023-06-01') TO ('2023-07-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_07 PARTITION OF minute_realtime FOR VALUES FROM ('2023-07-01') TO ('2023-08-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_08 PARTITION OF minute_realtime FOR VALUES FROM ('2023-08-01') TO ('2023-09-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_09 PARTITION OF minute_realtime FOR VALUES FROM ('2023-09-01') TO ('2023-10-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_10 PARTITION OF minute_realtime FOR VALUES FROM ('2023-10-01') TO ('2023-11-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_11 PARTITION OF minute_realtime FOR VALUES FROM ('2023-11-01') TO ('2023-12-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2023_12 PARTITION OF minute_realtime FOR VALUES FROM ('2023-12-01') TO ('2024-01-01');
-- 2024年分钟级分区
CREATE TABLE IF NOT EXISTS minute_realtime_2024_01 PARTITION OF minute_realtime FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_02 PARTITION OF minute_realtime FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_03 PARTITION OF minute_realtime FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_04 PARTITION OF minute_realtime FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_05 PARTITION OF minute_realtime FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_06 PARTITION OF minute_realtime FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_07 PARTITION OF minute_realtime FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_08 PARTITION OF minute_realtime FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_09 PARTITION OF minute_realtime FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_10 PARTITION OF minute_realtime FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_11 PARTITION OF minute_realtime FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2024_12 PARTITION OF minute_realtime FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
-- 2025年分钟级分区
CREATE TABLE IF NOT EXISTS minute_realtime_2025_01 PARTITION OF minute_realtime FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_02 PARTITION OF minute_realtime FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_03 PARTITION OF minute_realtime FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_04 PARTITION OF minute_realtime FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_05 PARTITION OF minute_realtime FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_06 PARTITION OF minute_realtime FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_07 PARTITION OF minute_realtime FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_08 PARTITION OF minute_realtime FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_09 PARTITION OF minute_realtime FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_10 PARTITION OF minute_realtime FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_11 PARTITION OF minute_realtime FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE IF NOT EXISTS minute_realtime_2025_12 PARTITION OF minute_realtime FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 小时级K线表
CREATE TABLE IF NOT EXISTS hour_realtime_2022_09 PARTITION OF hour_realtime FOR VALUES FROM ('2022-09-01') TO ('2022-10-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2022_10 PARTITION OF hour_realtime FOR VALUES FROM ('2022-10-01') TO ('2022-11-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2022_11 PARTITION OF hour_realtime FOR VALUES FROM ('2022-11-01') TO ('2022-12-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2022_12 PARTITION OF hour_realtime FOR VALUES FROM ('2022-12-01') TO ('2023-01-01');
-- 2023年小时级分区
CREATE TABLE IF NOT EXISTS hour_realtime_2023_01 PARTITION OF hour_realtime FOR VALUES FROM ('2023-01-01') TO ('2023-02-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_02 PARTITION OF hour_realtime FOR VALUES FROM ('2023-02-01') TO ('2023-03-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_03 PARTITION OF hour_realtime FOR VALUES FROM ('2023-03-01') TO ('2023-04-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_04 PARTITION OF hour_realtime FOR VALUES FROM ('2023-04-01') TO ('2023-05-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_05 PARTITION OF hour_realtime FOR VALUES FROM ('2023-05-01') TO ('2023-06-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_06 PARTITION OF hour_realtime FOR VALUES FROM ('2023-06-01') TO ('2023-07-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_07 PARTITION OF hour_realtime FOR VALUES FROM ('2023-07-01') TO ('2023-08-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_08 PARTITION OF hour_realtime FOR VALUES FROM ('2023-08-01') TO ('2023-09-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_09 PARTITION OF hour_realtime FOR VALUES FROM ('2023-09-01') TO ('2023-10-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_10 PARTITION OF hour_realtime FOR VALUES FROM ('2023-10-01') TO ('2023-11-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_11 PARTITION OF hour_realtime FOR VALUES FROM ('2023-11-01') TO ('2023-12-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2023_12 PARTITION OF hour_realtime FOR VALUES FROM ('2023-12-01') TO ('2024-01-01');
-- 2024年小时级分区
CREATE TABLE IF NOT EXISTS hour_realtime_2024_01 PARTITION OF hour_realtime FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_02 PARTITION OF hour_realtime FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_03 PARTITION OF hour_realtime FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_04 PARTITION OF hour_realtime FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_05 PARTITION OF hour_realtime FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_06 PARTITION OF hour_realtime FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_07 PARTITION OF hour_realtime FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_08 PARTITION OF hour_realtime FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_09 PARTITION OF hour_realtime FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_10 PARTITION OF hour_realtime FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_11 PARTITION OF hour_realtime FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2024_12 PARTITION OF hour_realtime FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
-- 2025年小时级分区
CREATE TABLE IF NOT EXISTS hour_realtime_2025_01 PARTITION OF hour_realtime FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_02 PARTITION OF hour_realtime FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_03 PARTITION OF hour_realtime FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_04 PARTITION OF hour_realtime FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_05 PARTITION OF hour_realtime FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_06 PARTITION OF hour_realtime FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_07 PARTITION OF hour_realtime FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_08 PARTITION OF hour_realtime FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_09 PARTITION OF hour_realtime FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_10 PARTITION OF hour_realtime FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_11 PARTITION OF hour_realtime FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE IF NOT EXISTS hour_realtime_2025_12 PARTITION OF hour_realtime FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');


-- 天级K线表
CREATE TABLE IF NOT EXISTS day_realtime_2022 PARTITION OF day_realtime FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE IF NOT EXISTS day_realtime_2023 PARTITION OF day_realtime FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE IF NOT EXISTS day_realtime_2024 PARTITION OF day_realtime FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE IF NOT EXISTS day_realtime_2025 PARTITION OF day_realtime FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');


-- 分钟级K线表索引
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2022_09_exchange_code_datetime ON minute_realtime_2022_09 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2022_10_exchange_code_datetime ON minute_realtime_2022_10 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2022_11_exchange_code_datetime ON minute_realtime_2022_11 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2022_12_exchange_code_datetime ON minute_realtime_2022_12 (exchange, code, datetime);
-- 2023年分钟级索引
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_01_exchange_code_datetime ON minute_realtime_2023_01 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_02_exchange_code_datetime ON minute_realtime_2023_02 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_03_exchange_code_datetime ON minute_realtime_2023_03 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_04_exchange_code_datetime ON minute_realtime_2023_04 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_05_exchange_code_datetime ON minute_realtime_2023_05 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_06_exchange_code_datetime ON minute_realtime_2023_06 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_07_exchange_code_datetime ON minute_realtime_2023_07 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_08_exchange_code_datetime ON minute_realtime_2023_08 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_09_exchange_code_datetime ON minute_realtime_2023_09 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_10_exchange_code_datetime ON minute_realtime_2023_10 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_11_exchange_code_datetime ON minute_realtime_2023_11 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2023_12_exchange_code_datetime ON minute_realtime_2023_12 (exchange, code, datetime);
-- 2024年分钟级索引
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_01_exchange_code_datetime ON minute_realtime_2024_01 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_02_exchange_code_datetime ON minute_realtime_2024_02 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_03_exchange_code_datetime ON minute_realtime_2024_03 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_04_exchange_code_datetime ON minute_realtime_2024_04 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_05_exchange_code_datetime ON minute_realtime_2024_05 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_06_exchange_code_datetime ON minute_realtime_2024_06 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_07_exchange_code_datetime ON minute_realtime_2024_07 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_08_exchange_code_datetime ON minute_realtime_2024_08 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_09_exchange_code_datetime ON minute_realtime_2024_09 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_10_exchange_code_datetime ON minute_realtime_2024_10 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_11_exchange_code_datetime ON minute_realtime_2024_11 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2024_12_exchange_code_datetime ON minute_realtime_2024_12 (exchange, code, datetime);
-- 2025年分钟级索引
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_01_exchange_code_datetime ON minute_realtime_2025_01 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_02_exchange_code_datetime ON minute_realtime_2025_02 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_03_exchange_code_datetime ON minute_realtime_2025_03 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_04_exchange_code_datetime ON minute_realtime_2025_04 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_05_exchange_code_datetime ON minute_realtime_2025_05 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_06_exchange_code_datetime ON minute_realtime_2025_06 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_07_exchange_code_datetime ON minute_realtime_2025_07 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_08_exchange_code_datetime ON minute_realtime_2025_08 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_09_exchange_code_datetime ON minute_realtime_2025_09 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_10_exchange_code_datetime ON minute_realtime_2025_10 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_11_exchange_code_datetime ON minute_realtime_2025_11 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_minute_realtime_2025_12_exchange_code_datetime ON minute_realtime_2025_12 (exchange, code, datetime);

-- 小时级K线表索引
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2022_09_exchange_code_datetime ON hour_realtime_2022_09 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2022_10_exchange_code_datetime ON hour_realtime_2022_10 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2022_11_exchange_code_datetime ON hour_realtime_2022_11 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2022_12_exchange_code_datetime ON hour_realtime_2022_12 (exchange, code, datetime);
-- 2023年小时级索引
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_01_exchange_code_datetime ON hour_realtime_2023_01 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_02_exchange_code_datetime ON hour_realtime_2023_02 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_03_exchange_code_datetime ON hour_realtime_2023_03 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_04_exchange_code_datetime ON hour_realtime_2023_04 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_05_exchange_code_datetime ON hour_realtime_2023_05 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_06_exchange_code_datetime ON hour_realtime_2023_06 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_07_exchange_code_datetime ON hour_realtime_2023_07 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_08_exchange_code_datetime ON hour_realtime_2023_08 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_09_exchange_code_datetime ON hour_realtime_2023_09 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_10_exchange_code_datetime ON hour_realtime_2023_10 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_11_exchange_code_datetime ON hour_realtime_2023_11 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2023_12_exchange_code_datetime ON hour_realtime_2023_12 (exchange, code, datetime);
-- 2024年小时级索引
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_01_exchange_code_datetime ON hour_realtime_2024_01 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_02_exchange_code_datetime ON hour_realtime_2024_02 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_03_exchange_code_datetime ON hour_realtime_2024_03 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_04_exchange_code_datetime ON hour_realtime_2024_04 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_05_exchange_code_datetime ON hour_realtime_2024_05 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_06_exchange_code_datetime ON hour_realtime_2024_06 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_07_exchange_code_datetime ON hour_realtime_2024_07 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_08_exchange_code_datetime ON hour_realtime_2024_08 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_09_exchange_code_datetime ON hour_realtime_2024_09 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_10_exchange_code_datetime ON hour_realtime_2024_10 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_11_exchange_code_datetime ON hour_realtime_2024_11 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2024_12_exchange_code_datetime ON hour_realtime_2024_12 (exchange, code, datetime);
-- 2025年小时级索引
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_01_exchange_code_datetime ON hour_realtime_2025_01 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_02_exchange_code_datetime ON hour_realtime_2025_02 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_03_exchange_code_datetime ON hour_realtime_2025_03 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_04_exchange_code_datetime ON hour_realtime_2025_04 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_05_exchange_code_datetime ON hour_realtime_2025_05 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_06_exchange_code_datetime ON hour_realtime_2025_06 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_07_exchange_code_datetime ON hour_realtime_2025_07 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_08_exchange_code_datetime ON hour_realtime_2025_08 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_09_exchange_code_datetime ON hour_realtime_2025_09 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_10_exchange_code_datetime ON hour_realtime_2025_10 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_11_exchange_code_datetime ON hour_realtime_2025_11 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_hour_realtime_2025_12_exchange_code_datetime ON hour_realtime_2025_12 (exchange, code, datetime);

-- 天级K线表索引
CREATE INDEX IF NOT EXISTS idx_day_realtime_2022_exchange_code_datetime ON day_realtime_2022 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_day_realtime_2023_exchange_code_datetime ON day_realtime_2023 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_day_realtime_2024_exchange_code_datetime ON day_realtime_2024 (exchange, code, datetime);
CREATE INDEX IF NOT EXISTS idx_day_realtime_2025_exchange_code_datetime ON day_realtime_2025 (exchange, code, datetime);