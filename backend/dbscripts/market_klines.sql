-- 要求：已安装 TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============ 原始 1m K 线表（Spot）============
-- 表: market_ohlcv_1m
CREATE TABLE IF NOT EXISTS public.market_ohlcv_1m (
    exchange text NOT NULL,
    symbol text NOT NULL,
    open_ts timestamptz NOT NULL,
    close_ts timestamptz NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    quote_volume numeric DEFAULT 0,
    taker_buy_volume numeric DEFAULT 0,
    taker_buy_qv numeric DEFAULT 0,
    number_of_trades int8 DEFAULT 0,
    is_final bool NOT NULL DEFAULT false,
    market_cap numeric DEFAULT NULL::numeric,
    PRIMARY KEY (exchange, symbol, open_ts)
);
COMMENT ON COLUMN public.market_ohlcv_1m.market_cap IS '市值数据，来源于market_crypto_listings表的market_cap字段';

-- 转为 hypertable：时间分区 open_ts
SELECT create_hypertable('market_ohlcv_1m', 'open_ts');

-- 常用索引
CREATE INDEX IF NOT EXISTS idx_market_ohlcv_1m_sym_close
  ON market_ohlcv_1m(exchange, symbol, close_ts DESC);

-- 保留策略（示例 400 天）
SELECT add_retention_policy('market_ohlcv_1m', INTERVAL '400 days');

-- ============ 连续聚合（Continuous Aggregates）============
-- 统一命名：market_ohlcv_<interval>

-- 3m
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_3m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('3 minutes', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_3m',
  start_offset => INTERVAL '2 days',
  end_offset   => INTERVAL '30 seconds',
  schedule_interval => INTERVAL '30 seconds'
);

-- 5m
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_5m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('5 minutes', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_5m',
  start_offset => INTERVAL '2 days',
  end_offset   => INTERVAL '30 seconds',
  schedule_interval => INTERVAL '30 seconds'
);

-- 15m
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_15m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('15 minutes', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_15m',
  start_offset => INTERVAL '7 days',
  end_offset   => INTERVAL '1 minute',
  schedule_interval => INTERVAL '1 minute'
);

-- 30m
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_30m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('30 minutes', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_30m',
  start_offset => INTERVAL '15 days',
  end_offset   => INTERVAL '2 minutes',
  schedule_interval => INTERVAL '2 minutes'
);

-- 1h
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_1h
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('1 hour', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_1h',
  start_offset => INTERVAL '30 days',
  end_offset   => INTERVAL '5 minutes',
  schedule_interval => INTERVAL '5 minutes'
);

-- 2h
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_2h
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('2 hours', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_2h',
  start_offset => INTERVAL '60 days',
  end_offset   => INTERVAL '10 minutes',
  schedule_interval => INTERVAL '10 minutes'
);

-- 4h
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_4h
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('4 hours', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_4h',
  start_offset => INTERVAL '60 days',
  end_offset   => INTERVAL '10 minutes',
  schedule_interval => INTERVAL '10 minutes'
);

-- 1d
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_1d
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('1 day', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_1d',
  start_offset => INTERVAL '400 days',
  end_offset   => INTERVAL '15 minutes',
  schedule_interval => INTERVAL '15 minutes'
);

-- 2d
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_2d
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('2 days', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_2d',
  start_offset => INTERVAL '800 days',
  end_offset   => INTERVAL '30 minutes',
  schedule_interval => INTERVAL '30 minutes'
);

-- 3d
CREATE MATERIALIZED VIEW IF NOT EXISTS market_ohlcv_3d
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
  exchange,
  symbol,
  time_bucket('3 days', open_ts) AS bucket,
  first(open, open_ts)  AS open,
  max(high)             AS high,
  min(low)              AS low,
  last(close, open_ts)  AS close,
  sum(volume)           AS volume,
  sum(quote_volume)     AS quote_volume,
  sum(taker_buy_volume) AS taker_buy_volume,
  sum(taker_buy_qv)     AS taker_buy_qv,
  sum(number_of_trades) AS number_of_trades,
  first(market_cap, open_ts) AS market_cap,
  CASE 
    WHEN first(market_cap, open_ts) > 0 THEN sum(quote_volume) / first(market_cap, open_ts)
    ELSE NULL
  END AS vmr,
  CASE 
    WHEN first(open, open_ts) > 0 THEN (last(close, open_ts) - first(open, open_ts)) / first(open, open_ts) * 100
    ELSE NULL
  END AS return_pct
FROM market_ohlcv_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
  'market_ohlcv_3d',
  start_offset => INTERVAL '1200 days',
  end_offset   => INTERVAL '45 minutes',
  schedule_interval => INTERVAL '45 minutes'
);
