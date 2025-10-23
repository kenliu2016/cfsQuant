-- 数据库DDL导出
-- 数据库: quant
-- 主机: localhost:5432
-- 导出时间: 2025-10-24 01:41:34
-- 导出内容: 表、视图、索引、序列等

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

-- === 扩展 ===
-- 扩展: timescaledb (版本: 2.22.1)
CREATE EXTENSION IF NOT EXISTS timescaledb WITH VERSION '2.22.1';


-- === 序列 ===
-- 序列: cron_log_id_seq
CREATE SEQUENCE IF NOT EXISTS public.cron_log_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_bull_bear_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_bull_bear_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_fear_greed_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_fear_greed_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_hmm_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_hmm_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_metrics_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_metrics_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_metrics_id_seq1
CREATE SEQUENCE IF NOT EXISTS public.indecator_metrics_id_seq1 START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_vmr_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_vmr_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: market_cap_id_seq
CREATE SEQUENCE IF NOT EXISTS public.market_cap_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: market_crypto_listings_id_seq
CREATE SEQUENCE IF NOT EXISTS public.market_crypto_listings_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: market_crypto_listings_id_seq1
CREATE SEQUENCE IF NOT EXISTS public.market_crypto_listings_id_seq1 START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: sys_strategies_id_seq
CREATE SEQUENCE IF NOT EXISTS public.sys_strategies_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;


-- === 表结构 ===
-- 表: backtest_equity_curve
CREATE TABLE IF NOT EXISTS public.backtest_equity_curve (
    run_id text,
    datetime timestamp,
    nav float8,
    drawdown float8,
    tenant_id varchar NOT NULL
);

-- 表: backtest_grid_levels
CREATE TABLE IF NOT EXISTS public.backtest_grid_levels (
    run_id text,
    level int8,
    price float8,
    name text,
    tenant_id varchar NOT NULL
);

-- 表: backtest_metrics
CREATE TABLE IF NOT EXISTS public.backtest_metrics (
    run_id varchar NOT NULL,
    metric_name varchar NOT NULL,
    metric_value float8,
    tenant_id varchar NOT NULL,
    PRIMARY KEY (run_id, metric_name)
);

-- 表: backtest_orders
CREATE TABLE IF NOT EXISTS public.backtest_orders (
    run_id varchar,
    datetime timestamp,
    code varchar,
    side varchar,
    qty float8,
    price float8,
    reason varchar,
    tenant_id varchar NOT NULL
);

-- 表: backtest_positions
CREATE TABLE IF NOT EXISTS public.backtest_positions (
    run_id varchar,
    datetime timestamp,
    code varchar,
    qty float8,
    avg_price float8,
    tenant_id varchar NOT NULL
);

-- 表: backtest_reports
CREATE TABLE IF NOT EXISTS public.backtest_reports (
    run_id varchar NOT NULL,
    report_path varchar,
    artifact_paths jsonb,
    tenant_id varchar NOT NULL,
    PRIMARY KEY (run_id)
);

-- 表: backtest_runs
CREATE TABLE IF NOT EXISTS public.backtest_runs (
    strategy varchar NOT NULL,
    code varchar NOT NULL,
    start_time timestamp NOT NULL,
    end_time timestamp NOT NULL,
    initial_capital float8 NOT NULL,
    final_capital float8 NOT NULL,
    created_at timestamp DEFAULT now(),
    run_id varchar NOT NULL,
    paras jsonb DEFAULT '{}'::jsonb,
    final_return float8,
    max_drawdown float8,
    sharpe float8,
    interval varchar,
    win_rate float8,
    trade_count int4,
    total_fee float8,
    total_profit float8,
    tenant_id varchar NOT NULL,
    created_by uuid,
    PRIMARY KEY (run_id)
);
COMMENT ON COLUMN public.backtest_runs.paras IS '执行策略时的参数，以JSON格式存储';
COMMENT ON COLUMN public.backtest_runs.win_rate IS '胜率 - 盈利交易占总交易的比例';
COMMENT ON COLUMN public.backtest_runs.trade_count IS '交易次数 - 总交易笔数';
COMMENT ON COLUMN public.backtest_runs.total_fee IS '总手续费 - 所有交易的手续费总和';
COMMENT ON COLUMN public.backtest_runs.total_profit IS '总收益 - 所有交易的盈亏总和';

-- 表: backtest_trades
CREATE TABLE IF NOT EXISTS public.backtest_trades (
    run_id varchar NOT NULL,
    datetime timestamp NOT NULL,
    code varchar NOT NULL,
    side varchar NOT NULL,
    price numeric NOT NULL,
    qty numeric NOT NULL,
    amount numeric NOT NULL,
    fee numeric NOT NULL,
    avg_price numeric,
    nav numeric,
    realized_pnl numeric,
    created_at timestamp DEFAULT now(),
    trade_type varchar NOT NULL DEFAULT 'normal'::character varying,
    drawdown float8,
    current_qty numeric,
    current_avg_price numeric,
    close_price numeric,
    current_cash numeric,
    tenant_id varchar NOT NULL
);
COMMENT ON COLUMN public.backtest_trades.nav IS '交易时的净资产价值(Net Asset Value)';
COMMENT ON COLUMN public.backtest_trades.trade_type IS '记录交易类型，如 ''normal'', ''take_profit'', ''stop_loss'' 等';
COMMENT ON COLUMN public.backtest_trades.drawdown IS '交易时的回撤比例';
COMMENT ON COLUMN public.backtest_trades.current_qty IS '交易后的数量';
COMMENT ON COLUMN public.backtest_trades.current_avg_price IS '交易后的平均价格';
COMMENT ON COLUMN public.backtest_trades.current_cash IS '交易后的现金余额';

-- 表: indecator_bull_bear
CREATE TABLE IF NOT EXISTS public.indecator_bull_bear (
    id int4 NOT NULL,
    exchange varchar NOT NULL,
    symbol varchar NOT NULL,
    datetime timestamp NOT NULL DEFAULT now(),
    score int4 NOT NULL,
    phase varchar NOT NULL,
    last_close numeric NOT NULL,
    ma_short numeric NOT NULL,
    ma_long numeric NOT NULL,
    vp_corr numeric NOT NULL,
    funding_rate numeric,
    stablecoin_flow numeric,
    reasons jsonb NOT NULL,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (exchange, symbol, datetime)
);
COMMENT ON COLUMN public.indecator_bull_bear.exchange IS '交易所名称';
COMMENT ON COLUMN public.indecator_bull_bear.symbol IS '交易对符号';
COMMENT ON COLUMN public.indecator_bull_bear.datetime IS '判定时间点';
COMMENT ON COLUMN public.indecator_bull_bear.score IS '综合评分分数';
COMMENT ON COLUMN public.indecator_bull_bear.phase IS '牛熊判定结果（Bull/Bear/Neutral）';
COMMENT ON COLUMN public.indecator_bull_bear.last_close IS '最新收盘价';
COMMENT ON COLUMN public.indecator_bull_bear.ma_short IS '短期移动平均线值';
COMMENT ON COLUMN public.indecator_bull_bear.ma_long IS '长期移动平均线值';
COMMENT ON COLUMN public.indecator_bull_bear.vp_corr IS '量价相关性系数';
COMMENT ON COLUMN public.indecator_bull_bear.funding_rate IS '资金费率';
COMMENT ON COLUMN public.indecator_bull_bear.stablecoin_flow IS '稳定币流入量';
COMMENT ON COLUMN public.indecator_bull_bear.reasons IS '判定原因列表（JSON格式）';
COMMENT ON COLUMN public.indecator_bull_bear.created_at IS '记录创建时间';

-- 表: indecator_bull_bear_metrics
CREATE TABLE IF NOT EXISTS public.indecator_bull_bear_metrics (
    id int4 NOT NULL,
    exchange varchar NOT NULL,
    symbol varchar NOT NULL,
    datetime timestamp NOT NULL DEFAULT now(),
    funding_rate numeric,
    stablecoin_flow numeric,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);

-- 表: indecator_fear_greed
CREATE TABLE IF NOT EXISTS public.indecator_fear_greed (
    id int4 NOT NULL,
    datetime timestamp NOT NULL,
    value int4 NOT NULL,
    value_classification varchar NOT NULL,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);
COMMENT ON COLUMN public.indecator_fear_greed.datetime IS '数据时间点';
COMMENT ON COLUMN public.indecator_fear_greed.value IS '恐惧贪婪指数值';
COMMENT ON COLUMN public.indecator_fear_greed.value_classification IS '情绪分类（如：Extreme Fear, Fear, Neutral, Greed, Extreme Greed）';

-- 表: indecator_hmm
CREATE TABLE IF NOT EXISTS public.indecator_hmm (
    id int4 NOT NULL,
    exchange varchar NOT NULL,
    symbol varchar NOT NULL,
    datetime timestamp NOT NULL,
    state int4 NOT NULL,
    probability numeric NOT NULL,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);
COMMENT ON COLUMN public.indecator_hmm.exchange IS '交易所名称';
COMMENT ON COLUMN public.indecator_hmm.symbol IS '交易对符号';
COMMENT ON COLUMN public.indecator_hmm.datetime IS '状态识别时间点';
COMMENT ON COLUMN public.indecator_hmm.state IS 'HMM模型识别的状态编号';
COMMENT ON COLUMN public.indecator_hmm.probability IS '状态概率';

-- 表: indecator_vmr
CREATE TABLE IF NOT EXISTS public.indecator_vmr (
    id int4 NOT NULL,
    code varchar NOT NULL,
    timeframe varchar NOT NULL,
    datetime timestamp NOT NULL,
    vmr numeric NOT NULL,
    volume numeric NOT NULL,
    price_change numeric NOT NULL,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);
COMMENT ON COLUMN public.indecator_vmr.code IS '交易对代码';
COMMENT ON COLUMN public.indecator_vmr.timeframe IS '时间周期（如：1h, 4h, 1d等）';
COMMENT ON COLUMN public.indecator_vmr.datetime IS '指标计算时间点';
COMMENT ON COLUMN public.indecator_vmr.vmr IS '成交量动量比率值';
COMMENT ON COLUMN public.indecator_vmr.volume IS '成交量';
COMMENT ON COLUMN public.indecator_vmr.price_change IS '价格变化';

-- 表: market_codes
CREATE TABLE IF NOT EXISTS public.market_codes (
    exchange text NOT NULL,
    code text NOT NULL,
    active bool NOT NULL DEFAULT false,
    excode text NOT NULL DEFAULT 1,
    watch bool NOT NULL DEFAULT false,
    basecurrency text,
    quotecurrency text,
    created_at timestamptz DEFAULT timezone('utc'::text, now()),
    updated_at timestamptz DEFAULT timezone('utc'::text, now()),
    PRIMARY KEY (exchange, code)
);

-- 表: market_crypto_listings - 市场加密货币列表数据表
CREATE TABLE IF NOT EXISTS public.market_crypto_listings (
    id int4 NOT NULL,
    crypto_id int4 NOT NULL,
    name varchar NOT NULL,
    symbol varchar NOT NULL,
    slug varchar,
    cmc_rank int4,
    circulating_supply numeric,
    total_supply numeric,
    max_supply numeric,
    infinite_supply bool DEFAULT false,
    last_updated timestamptz,
    date_added timestamptz,
    tags jsonb,
    price numeric,
    volume_24h numeric,
    volume_change_24h numeric,
    percent_change_1h numeric,
    percent_change_24h numeric,
    percent_change_7d numeric,
    market_cap numeric,
    market_cap_dominance numeric,
    fully_diluted_market_cap numeric,
    quote_last_updated timestamptz,
    data_timestamp timestamptz NOT NULL,
    created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz DEFAULT CURRENT_TIMESTAMP,
    vmr_24h numeric,
    PRIMARY KEY (id),
    UNIQUE (crypto_id, symbol)
);
COMMENT ON COLUMN public.market_crypto_listings.crypto_id IS '加密货币ID';
COMMENT ON COLUMN public.market_crypto_listings.name IS '加密货币名称';
COMMENT ON COLUMN public.market_crypto_listings.symbol IS '加密货币符号';
COMMENT ON COLUMN public.market_crypto_listings.slug IS 'URL slug';
COMMENT ON COLUMN public.market_crypto_listings.cmc_rank IS '市场排名';
COMMENT ON COLUMN public.market_crypto_listings.circulating_supply IS '流通供应量';
COMMENT ON COLUMN public.market_crypto_listings.total_supply IS '总供应量';
COMMENT ON COLUMN public.market_crypto_listings.max_supply IS '最大供应量';
COMMENT ON COLUMN public.market_crypto_listings.infinite_supply IS '是否无限供应';
COMMENT ON COLUMN public.market_crypto_listings.last_updated IS '数据最后更新时间';
COMMENT ON COLUMN public.market_crypto_listings.date_added IS '添加时间';
COMMENT ON COLUMN public.market_crypto_listings.tags IS '标签列表（JSON格式）';
COMMENT ON COLUMN public.market_crypto_listings.price IS '价格（USD）';
COMMENT ON COLUMN public.market_crypto_listings.volume_24h IS '24小时交易量';
COMMENT ON COLUMN public.market_crypto_listings.volume_change_24h IS '24小时交易量变化百分比';
COMMENT ON COLUMN public.market_crypto_listings.percent_change_1h IS '1小时价格变化百分比';
COMMENT ON COLUMN public.market_crypto_listings.percent_change_24h IS '24小时价格变化百分比';
COMMENT ON COLUMN public.market_crypto_listings.percent_change_7d IS '7天价格变化百分比';
COMMENT ON COLUMN public.market_crypto_listings.market_cap IS '市值';
COMMENT ON COLUMN public.market_crypto_listings.market_cap_dominance IS '市值占比';
COMMENT ON COLUMN public.market_crypto_listings.fully_diluted_market_cap IS '完全稀释市值';
COMMENT ON COLUMN public.market_crypto_listings.quote_last_updated IS '报价最后更新时间';
COMMENT ON COLUMN public.market_crypto_listings.data_timestamp IS '数据采集时间戳';
COMMENT ON TABLE public.market_crypto_listings IS '市场加密货币列表数据表';

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
    datetime timestamptz NOT NULL,
    PRIMARY KEY (exchange, symbol, open_ts)
);
COMMENT ON COLUMN public.market_ohlcv_1m.market_cap IS '市值数据，来源于market_crypto_listings表的market_cap字段';

-- 表: market_ohlcv_1m_backup
CREATE TABLE IF NOT EXISTS public.market_ohlcv_1m_backup (
    exchange text,
    symbol text,
    open_ts timestamptz,
    close_ts timestamptz,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume numeric,
    quote_volume numeric,
    taker_buy_volume numeric,
    taker_buy_qv numeric,
    number_of_trades int8,
    is_final bool,
    market_cap numeric,
    datetime timestamptz
);

-- 表: sys_cron_log
CREATE TABLE IF NOT EXISTS public.sys_cron_log (
    id int4 NOT NULL,
    job_name text,
    status text,
    message text,
    started_at timestamp,
    ended_at timestamp,
    PRIMARY KEY (id)
);

-- 表: sys_strategies
CREATE TABLE IF NOT EXISTS public.sys_strategies (
    id int4 NOT NULL,
    name text NOT NULL,
    description text,
    params jsonb DEFAULT '{}'::jsonb,
    created_at timestamp DEFAULT now(),
    tenant_id varchar NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (name),
    UNIQUE (tenant_id, name)
);

-- 表: tenant_audit_logs
CREATE TABLE IF NOT EXISTS public.tenant_audit_logs (
    id uuid NOT NULL,
    tenant_id varchar NOT NULL,
    user_id uuid,
    role text,
    method text NOT NULL,
    path text NOT NULL,
    query text,
    status_code int4,
    user_agent text,
    ip_address text,
    created_at timestamp DEFAULT now(),
    extra jsonb DEFAULT '{}'::jsonb,
    PRIMARY KEY (id)
);

-- 表: tenant_exchange_accounts
CREATE TABLE IF NOT EXISTS public.tenant_exchange_accounts (
    id uuid NOT NULL,
    tenant_id varchar NOT NULL,
    exchange varchar NOT NULL,
    label varchar,
    api_key varchar NOT NULL,
    api_secret varchar NOT NULL,
    api_passphrase varchar,
    extra jsonb DEFAULT '{}'::jsonb,
    is_active bool DEFAULT true,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    owner_user_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb,
    PRIMARY KEY (id)
);

-- 表: tenant_users
CREATE TABLE IF NOT EXISTS public.tenant_users (
    id uuid NOT NULL,
    tenant_id varchar NOT NULL,
    email varchar NOT NULL,
    hashed_password varchar NOT NULL,
    full_name varchar,
    is_admin bool DEFAULT false,
    is_active bool DEFAULT true,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    is_super_admin bool DEFAULT false,
    PRIMARY KEY (id),
    UNIQUE (tenant_id, email),
    UNIQUE (tenant_id, id)
);

-- 表: tenants
CREATE TABLE IF NOT EXISTS public.tenants (
    tenant_id varchar NOT NULL,
    name varchar NOT NULL,
    description text,
    is_active bool DEFAULT true,
    settings jsonb DEFAULT '{}'::jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (tenant_id)
);

-- 表: tuning_results
CREATE TABLE IF NOT EXISTS public.tuning_results (
    task_id varchar NOT NULL,
    run_id varchar NOT NULL,
    params jsonb,
    created_at timestamp DEFAULT now(),
    tenant_id varchar NOT NULL,
    PRIMARY KEY (tenant_id, run_id, task_id)
);

-- 表: tuning_tasks
CREATE TABLE IF NOT EXISTS public.tuning_tasks (
    task_id varchar NOT NULL,
    strategy text,
    status text,
    total int4,
    finished int4,
    created_at timestamp DEFAULT now(),
    start_time timestamp,
    timeout timestamp,
    error text,
    code text,
    interval text,
    end_time timestamp,
    params text,
    tenant_id varchar NOT NULL,
    PRIMARY KEY (tenant_id, task_id)
);


-- === 视图 ===
-- 视图: market_ohlcv_15m
CREATE OR REPLACE VIEW public.market_ohlcv_15m AS
 SELECT _materialized_hypertable_14.exchange,
    _materialized_hypertable_14.symbol,
    _materialized_hypertable_14.bucket,
    _materialized_hypertable_14.open,
    _materialized_hypertable_14.high,
    _materialized_hypertable_14.low,
    _materialized_hypertable_14.close,
    _materialized_hypertable_14.volume,
    _materialized_hypertable_14.quote_volume,
    _materialized_hypertable_14.taker_buy_volume,
    _materialized_hypertable_14.taker_buy_qv,
    _materialized_hypertable_14.number_of_trades,
    _materialized_hypertable_14.market_cap,
    _materialized_hypertable_14.vmr
   FROM _timescaledb_internal._materialized_hypertable_14
  WHERE _materialized_hypertable_14.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(14)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('00:15:00'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(14)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('00:15:00'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_1d
CREATE OR REPLACE VIEW public.market_ohlcv_1d AS
 SELECT _materialized_hypertable_19.exchange,
    _materialized_hypertable_19.symbol,
    _materialized_hypertable_19.bucket,
    _materialized_hypertable_19.open,
    _materialized_hypertable_19.high,
    _materialized_hypertable_19.low,
    _materialized_hypertable_19.close,
    _materialized_hypertable_19.volume,
    _materialized_hypertable_19.quote_volume,
    _materialized_hypertable_19.taker_buy_volume,
    _materialized_hypertable_19.taker_buy_qv,
    _materialized_hypertable_19.number_of_trades,
    _materialized_hypertable_19.market_cap,
    _materialized_hypertable_19.vmr
   FROM _timescaledb_internal._materialized_hypertable_19
  WHERE _materialized_hypertable_19.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(19)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('1 day'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(19)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('1 day'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_1h
CREATE OR REPLACE VIEW public.market_ohlcv_1h AS
 SELECT _materialized_hypertable_16.exchange,
    _materialized_hypertable_16.symbol,
    _materialized_hypertable_16.bucket,
    _materialized_hypertable_16.open,
    _materialized_hypertable_16.high,
    _materialized_hypertable_16.low,
    _materialized_hypertable_16.close,
    _materialized_hypertable_16.volume,
    _materialized_hypertable_16.quote_volume,
    _materialized_hypertable_16.taker_buy_volume,
    _materialized_hypertable_16.taker_buy_qv,
    _materialized_hypertable_16.number_of_trades,
    _materialized_hypertable_16.market_cap,
    _materialized_hypertable_16.vmr
   FROM _timescaledb_internal._materialized_hypertable_16
  WHERE _materialized_hypertable_16.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(16)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('01:00:00'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(16)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('01:00:00'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_2d
CREATE OR REPLACE VIEW public.market_ohlcv_2d AS
 SELECT _materialized_hypertable_20.exchange,
    _materialized_hypertable_20.symbol,
    _materialized_hypertable_20.bucket,
    _materialized_hypertable_20.open,
    _materialized_hypertable_20.high,
    _materialized_hypertable_20.low,
    _materialized_hypertable_20.close,
    _materialized_hypertable_20.volume,
    _materialized_hypertable_20.quote_volume,
    _materialized_hypertable_20.taker_buy_volume,
    _materialized_hypertable_20.taker_buy_qv,
    _materialized_hypertable_20.number_of_trades,
    _materialized_hypertable_20.market_cap,
    _materialized_hypertable_20.vmr
   FROM _timescaledb_internal._materialized_hypertable_20
  WHERE _materialized_hypertable_20.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(20)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('2 days'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(20)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('2 days'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_2h
CREATE OR REPLACE VIEW public.market_ohlcv_2h AS
 SELECT _materialized_hypertable_17.exchange,
    _materialized_hypertable_17.symbol,
    _materialized_hypertable_17.bucket,
    _materialized_hypertable_17.open,
    _materialized_hypertable_17.high,
    _materialized_hypertable_17.low,
    _materialized_hypertable_17.close,
    _materialized_hypertable_17.volume,
    _materialized_hypertable_17.quote_volume,
    _materialized_hypertable_17.taker_buy_volume,
    _materialized_hypertable_17.taker_buy_qv,
    _materialized_hypertable_17.number_of_trades,
    _materialized_hypertable_17.market_cap,
    _materialized_hypertable_17.vmr
   FROM _timescaledb_internal._materialized_hypertable_17
  WHERE _materialized_hypertable_17.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(17)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('02:00:00'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(17)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('02:00:00'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_30m
CREATE OR REPLACE VIEW public.market_ohlcv_30m AS
 SELECT _materialized_hypertable_15.exchange,
    _materialized_hypertable_15.symbol,
    _materialized_hypertable_15.bucket,
    _materialized_hypertable_15.open,
    _materialized_hypertable_15.high,
    _materialized_hypertable_15.low,
    _materialized_hypertable_15.close,
    _materialized_hypertable_15.volume,
    _materialized_hypertable_15.quote_volume,
    _materialized_hypertable_15.taker_buy_volume,
    _materialized_hypertable_15.taker_buy_qv,
    _materialized_hypertable_15.number_of_trades,
    _materialized_hypertable_15.market_cap,
    _materialized_hypertable_15.vmr
   FROM _timescaledb_internal._materialized_hypertable_15
  WHERE _materialized_hypertable_15.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(15)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('00:30:00'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(15)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('00:30:00'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_3d
CREATE OR REPLACE VIEW public.market_ohlcv_3d AS
 SELECT _materialized_hypertable_21.exchange,
    _materialized_hypertable_21.symbol,
    _materialized_hypertable_21.bucket,
    _materialized_hypertable_21.open,
    _materialized_hypertable_21.high,
    _materialized_hypertable_21.low,
    _materialized_hypertable_21.close,
    _materialized_hypertable_21.volume,
    _materialized_hypertable_21.quote_volume,
    _materialized_hypertable_21.taker_buy_volume,
    _materialized_hypertable_21.taker_buy_qv,
    _materialized_hypertable_21.number_of_trades,
    _materialized_hypertable_21.market_cap,
    _materialized_hypertable_21.vmr
   FROM _timescaledb_internal._materialized_hypertable_21
  WHERE _materialized_hypertable_21.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(21)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('3 days'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(21)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('3 days'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_3m
CREATE OR REPLACE VIEW public.market_ohlcv_3m AS
 SELECT _materialized_hypertable_12.exchange,
    _materialized_hypertable_12.symbol,
    _materialized_hypertable_12.bucket,
    _materialized_hypertable_12.open,
    _materialized_hypertable_12.high,
    _materialized_hypertable_12.low,
    _materialized_hypertable_12.close,
    _materialized_hypertable_12.volume,
    _materialized_hypertable_12.quote_volume,
    _materialized_hypertable_12.taker_buy_volume,
    _materialized_hypertable_12.taker_buy_qv,
    _materialized_hypertable_12.number_of_trades,
    _materialized_hypertable_12.market_cap,
    _materialized_hypertable_12.vmr
   FROM _timescaledb_internal._materialized_hypertable_12
  WHERE _materialized_hypertable_12.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(12)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('00:03:00'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(12)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('00:03:00'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_4h
CREATE OR REPLACE VIEW public.market_ohlcv_4h AS
 SELECT _materialized_hypertable_18.exchange,
    _materialized_hypertable_18.symbol,
    _materialized_hypertable_18.bucket,
    _materialized_hypertable_18.open,
    _materialized_hypertable_18.high,
    _materialized_hypertable_18.low,
    _materialized_hypertable_18.close,
    _materialized_hypertable_18.volume,
    _materialized_hypertable_18.quote_volume,
    _materialized_hypertable_18.taker_buy_volume,
    _materialized_hypertable_18.taker_buy_qv,
    _materialized_hypertable_18.number_of_trades,
    _materialized_hypertable_18.market_cap,
    _materialized_hypertable_18.vmr
   FROM _timescaledb_internal._materialized_hypertable_18
  WHERE _materialized_hypertable_18.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(18)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('04:00:00'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(18)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('04:00:00'::interval, market_ohlcv_1m.open_ts));;

-- 视图: market_ohlcv_5m
CREATE OR REPLACE VIEW public.market_ohlcv_5m AS
 SELECT _materialized_hypertable_13.exchange,
    _materialized_hypertable_13.symbol,
    _materialized_hypertable_13.bucket,
    _materialized_hypertable_13.open,
    _materialized_hypertable_13.high,
    _materialized_hypertable_13.low,
    _materialized_hypertable_13.close,
    _materialized_hypertable_13.volume,
    _materialized_hypertable_13.quote_volume,
    _materialized_hypertable_13.taker_buy_volume,
    _materialized_hypertable_13.taker_buy_qv,
    _materialized_hypertable_13.number_of_trades,
    _materialized_hypertable_13.market_cap,
    _materialized_hypertable_13.vmr
   FROM _timescaledb_internal._materialized_hypertable_13
  WHERE _materialized_hypertable_13.bucket < COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(13)), '-infinity'::timestamp with time zone)
UNION ALL
 SELECT market_ohlcv_1m.exchange,
    market_ohlcv_1m.symbol,
    time_bucket('00:05:00'::interval, market_ohlcv_1m.open_ts) AS bucket,
    first(market_ohlcv_1m.open, market_ohlcv_1m.open_ts) AS open,
    max(market_ohlcv_1m.high) AS high,
    min(market_ohlcv_1m.low) AS low,
    last(market_ohlcv_1m.close, market_ohlcv_1m.open_ts) AS close,
    sum(market_ohlcv_1m.volume) AS volume,
    sum(market_ohlcv_1m.quote_volume) AS quote_volume,
    sum(market_ohlcv_1m.taker_buy_volume) AS taker_buy_volume,
    sum(market_ohlcv_1m.taker_buy_qv) AS taker_buy_qv,
    sum(market_ohlcv_1m.number_of_trades) AS number_of_trades,
    first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) AS market_cap,
        CASE
            WHEN first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts) > 0::numeric THEN sum(market_ohlcv_1m.quote_volume) / first(market_ohlcv_1m.market_cap, market_ohlcv_1m.open_ts)
            ELSE NULL::numeric
        END AS vmr
   FROM market_ohlcv_1m
  WHERE market_ohlcv_1m.open_ts >= COALESCE(_timescaledb_functions.to_timestamp(_timescaledb_functions.cagg_watermark(13)), '-infinity'::timestamp with time zone)
  GROUP BY market_ohlcv_1m.exchange, market_ohlcv_1m.symbol, (time_bucket('00:05:00'::interval, market_ohlcv_1m.open_ts));;


-- === 索引 ===
-- 索引: idx_backtest_equity_curve_tenant_run (表: backtest_equity_curve)
CREATE INDEX idx_backtest_equity_curve_tenant_run ON public.backtest_equity_curve USING btree (tenant_id, run_id, datetime);

-- 索引: idx_backtest_grid_levels_tenant_run (表: backtest_grid_levels)
CREATE INDEX idx_backtest_grid_levels_tenant_run ON public.backtest_grid_levels USING btree (tenant_id, run_id);

-- 索引: idx_backtest_metrics_run (表: backtest_metrics)
CREATE INDEX idx_backtest_metrics_run ON public.backtest_metrics USING btree (run_id);

-- 索引: idx_backtest_metrics_tenant_run (表: backtest_metrics)
CREATE INDEX idx_backtest_metrics_tenant_run ON public.backtest_metrics USING btree (tenant_id, run_id, metric_name);

-- 索引: idx_backtest_runs_created_by (表: backtest_runs)
CREATE INDEX idx_backtest_runs_created_by ON public.backtest_runs USING btree (tenant_id, created_by, created_at DESC);

-- 索引: idx_backtest_runs_tenant_created_at (表: backtest_runs)
CREATE INDEX idx_backtest_runs_tenant_created_at ON public.backtest_runs USING btree (tenant_id, created_at DESC);

-- 索引: idx_backtest_runs_tenant_strategy (表: backtest_runs)
CREATE INDEX idx_backtest_runs_tenant_strategy ON public.backtest_runs USING btree (tenant_id, strategy, created_at DESC);

-- 索引: idx_runs_code (表: backtest_runs)
CREATE INDEX idx_runs_code ON public.backtest_runs USING btree (code);

-- 索引: idx_runs_strategy (表: backtest_runs)
CREATE INDEX idx_runs_strategy ON public.backtest_runs USING btree (strategy);

-- 索引: idx_backtest_trades_tenant_run (表: backtest_trades)
CREATE INDEX idx_backtest_trades_tenant_run ON public.backtest_trades USING btree (tenant_id, run_id, datetime);

-- 索引: idx_indecator_bull_bear_datetime (表: indecator_bull_bear)
CREATE INDEX idx_indecator_bull_bear_datetime ON public.indecator_bull_bear USING btree (datetime);

-- 索引: idx_indecator_bull_bear_exchange_symbol (表: indecator_bull_bear)
CREATE INDEX idx_indecator_bull_bear_exchange_symbol ON public.indecator_bull_bear USING btree (exchange, symbol);

-- 索引: idx_indecator_bull_bear_phase (表: indecator_bull_bear)
CREATE INDEX idx_indecator_bull_bear_phase ON public.indecator_bull_bear USING btree (phase);

-- 索引: idx_indecator_bull_bear_score (表: indecator_bull_bear)
CREATE INDEX idx_indecator_bull_bear_score ON public.indecator_bull_bear USING btree (score);

-- 索引: indecator_bull_bear_metrics_idx (表: indecator_bull_bear_metrics)
CREATE INDEX indecator_bull_bear_metrics_idx ON public.indecator_bull_bear_metrics USING btree (exchange, symbol, datetime);

-- 索引: indecator_metrics_idx (表: indecator_bull_bear_metrics)
CREATE INDEX indecator_metrics_idx ON public.indecator_bull_bear_metrics USING btree (exchange, symbol, datetime);

-- 索引: idx_vmr_metrics_code_timeframe_datetime (表: indecator_vmr)
CREATE INDEX idx_vmr_metrics_code_timeframe_datetime ON public.indecator_vmr USING btree (code, timeframe, datetime);

-- 索引: idx_market_crypto_cmc_rank (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_cmc_rank ON public.market_crypto_listings USING btree (cmc_rank);

-- 索引: idx_market_crypto_crypto_id (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_crypto_id ON public.market_crypto_listings USING btree (crypto_id);

-- 索引: idx_market_crypto_data_timestamp (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_data_timestamp ON public.market_crypto_listings USING btree (data_timestamp);

-- 索引: idx_market_crypto_last_updated (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_last_updated ON public.market_crypto_listings USING btree (last_updated);

-- 索引: idx_market_crypto_market_cap (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_market_cap ON public.market_crypto_listings USING btree (market_cap);

-- 索引: idx_market_crypto_price (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_price ON public.market_crypto_listings USING btree (price);

-- 索引: idx_market_crypto_rank_timestamp (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_rank_timestamp ON public.market_crypto_listings USING btree (cmc_rank, data_timestamp);

-- 索引: idx_market_crypto_symbol (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_symbol ON public.market_crypto_listings USING btree (symbol);

-- 索引: idx_market_crypto_symbol_timestamp (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_symbol_timestamp ON public.market_crypto_listings USING btree (symbol, data_timestamp);

-- 索引: idx_market_crypto_tags (表: market_crypto_listings)
CREATE INDEX idx_market_crypto_tags ON public.market_crypto_listings USING gin (tags);

-- 索引: idx_market_ohlcv_1m_base_symbol (表: market_ohlcv_1m)
CREATE INDEX idx_market_ohlcv_1m_base_symbol ON public.market_ohlcv_1m USING btree (exchange, get_base_symbol(symbol));

-- 索引: idx_market_ohlcv_1m_datetime (表: market_ohlcv_1m)
CREATE INDEX idx_market_ohlcv_1m_datetime ON public.market_ohlcv_1m USING btree (datetime);

-- 索引: idx_market_ohlcv_1m_sym_close (表: market_ohlcv_1m)
CREATE INDEX idx_market_ohlcv_1m_sym_close ON public.market_ohlcv_1m USING btree (exchange, symbol, close_ts DESC);

-- 索引: market_ohlcv_1m_open_ts_idx (表: market_ohlcv_1m)
CREATE INDEX market_ohlcv_1m_open_ts_idx ON public.market_ohlcv_1m USING btree (open_ts DESC);

-- 索引: idx_tenant_audit_logs_tenant_created (表: tenant_audit_logs)
CREATE INDEX idx_tenant_audit_logs_tenant_created ON public.tenant_audit_logs USING btree (tenant_id, created_at DESC);

-- 索引: idx_tenant_audit_logs_user_created (表: tenant_audit_logs)
CREATE INDEX idx_tenant_audit_logs_user_created ON public.tenant_audit_logs USING btree (tenant_id, user_id, created_at DESC);

-- 索引: idx_exchange_accounts_owner (表: tenant_exchange_accounts)
CREATE INDEX idx_exchange_accounts_owner ON public.tenant_exchange_accounts USING btree (tenant_id, owner_user_id);

-- 索引: idx_tenant_exchange_accounts_active (表: tenant_exchange_accounts)
CREATE INDEX idx_tenant_exchange_accounts_active ON public.tenant_exchange_accounts USING btree (tenant_id, is_active);

-- 索引: idx_tenant_users_active (表: tenant_users)
CREATE INDEX idx_tenant_users_active ON public.tenant_users USING btree (tenant_id, is_active);

-- 索引: idx_tuning_results_task (表: tuning_results)
CREATE INDEX idx_tuning_results_task ON public.tuning_results USING btree (task_id);

-- 索引: idx_tuning_results_tenant_task (表: tuning_results)
CREATE INDEX idx_tuning_results_tenant_task ON public.tuning_results USING btree (tenant_id, task_id, created_at);

-- 索引: idx_tuning_tasks_code (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_code ON public.tuning_tasks USING btree (code);

-- 索引: idx_tuning_tasks_interval (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_interval ON public.tuning_tasks USING btree ("interval");

-- 索引: idx_tuning_tasks_start_end_time (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_start_end_time ON public.tuning_tasks USING btree (start_time, end_time);

-- 索引: idx_tuning_tasks_start_time (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_start_time ON public.tuning_tasks USING btree (start_time);

-- 索引: idx_tuning_tasks_status (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_status ON public.tuning_tasks USING btree (status);

-- 索引: idx_tuning_tasks_tenant_status (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_tenant_status ON public.tuning_tasks USING btree (tenant_id, status, created_at);

-- 索引: idx_tuning_tasks_timeout (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_timeout ON public.tuning_tasks USING btree (timeout);


-- === 触发器 ===
-- 触发器: ts_cagg_invalidation_trigger (表: market_ohlcv_1m)
CREATE TRIGGER ts_cagg_invalidation_trigger AFTER INSERT OR DELETE OR UPDATE ON public.market_ohlcv_1m FOR EACH ROW EXECUTE FUNCTION _timescaledb_functions.continuous_agg_invalidation_trigger('1');

-- 触发器: ts_insert_blocker (表: market_ohlcv_1m)
CREATE TRIGGER ts_insert_blocker BEFORE INSERT ON public.market_ohlcv_1m FOR EACH ROW EXECUTE FUNCTION _timescaledb_functions.insert_blocker();


-- === 函数 ===
-- 函数: add_columnstore_policy (无法获取函数定义)

-- 函数: add_compression_policy (无法获取函数定义)

-- 函数: add_continuous_aggregate_policy (无法获取函数定义)

-- 函数: add_dimension (无法获取函数定义)

-- 函数: add_dimension (无法获取函数定义)

-- 函数: add_job (无法获取函数定义)

-- 函数: add_process_hypertable_invalidations_policy (无法获取函数定义)

-- 函数: add_reorder_policy (无法获取函数定义)

-- 函数: add_retention_policy (无法获取函数定义)

-- 函数: alter_job (无法获取函数定义)

-- 函数: approximate_row_count (无法获取函数定义)

-- 函数: attach_chunk (无法获取函数定义)

-- 函数: attach_tablespace (无法获取函数定义)

-- 函数: by_hash (无法获取函数定义)

-- 函数: by_range (无法获取函数定义)

-- 函数: cagg_migrate (无法获取函数定义)

-- 函数: chunk_columnstore_stats (无法获取函数定义)

-- 函数: chunk_compression_stats (无法获取函数定义)

-- 函数: chunks_detailed_size (无法获取函数定义)

-- 函数: compress_chunk (无法获取函数定义)

-- 函数: convert_to_columnstore (无法获取函数定义)

-- 函数: convert_to_rowstore (无法获取函数定义)

-- 函数: create_hypertable (无法获取函数定义)

-- 函数: create_hypertable (无法获取函数定义)

-- 函数: decompress_chunk (无法获取函数定义)

-- 函数: delete_job (无法获取函数定义)

-- 函数: detach_chunk (无法获取函数定义)

-- 函数: detach_tablespace (无法获取函数定义)

-- 函数: detach_tablespaces (无法获取函数定义)

-- 函数: disable_chunk_skipping (无法获取函数定义)

-- 函数: drop_chunks (无法获取函数定义)

-- 函数: enable_chunk_skipping (无法获取函数定义)

-- 函数: first (无法获取函数定义)

-- 函数: generate_uuidv7 (无法获取函数定义)

-- 函数: get_base_symbol (无法获取函数定义)

-- 函数: get_multiple_symbols_market_cap (无法获取函数定义)

-- 函数: get_symbol_market_cap_history (无法获取函数定义)

-- 函数: get_telemetry_report (无法获取函数定义)

-- 函数: histogram (无法获取函数定义)

-- 函数: hypertable_approximate_detailed_size (无法获取函数定义)

-- 函数: hypertable_approximate_size (无法获取函数定义)

-- 函数: hypertable_columnstore_stats (无法获取函数定义)

-- 函数: hypertable_compression_stats (无法获取函数定义)

-- 函数: hypertable_detailed_size (无法获取函数定义)

-- 函数: hypertable_index_size (无法获取函数定义)

-- 函数: hypertable_size (无法获取函数定义)

-- 函数: interpolate (无法获取函数定义)

-- 函数: interpolate (无法获取函数定义)

-- 函数: interpolate (无法获取函数定义)

-- 函数: interpolate (无法获取函数定义)

-- 函数: interpolate (无法获取函数定义)

-- 函数: last (无法获取函数定义)

-- 函数: locf (无法获取函数定义)

-- 函数: merge_chunks (无法获取函数定义)

-- 函数: merge_chunks (无法获取函数定义)

-- 函数: move_chunk (无法获取函数定义)

-- 函数: recompress_chunk (无法获取函数定义)

-- 函数: refresh_continuous_aggregate (无法获取函数定义)

-- 函数: remove_columnstore_policy (无法获取函数定义)

-- 函数: remove_compression_policy (无法获取函数定义)

-- 函数: remove_continuous_aggregate_policy (无法获取函数定义)

-- 函数: remove_process_hypertable_invalidations_policy (无法获取函数定义)

-- 函数: remove_reorder_policy (无法获取函数定义)

-- 函数: remove_retention_policy (无法获取函数定义)

-- 函数: reorder_chunk (无法获取函数定义)

-- 函数: run_job (无法获取函数定义)

-- 函数: set_adaptive_chunking (无法获取函数定义)

-- 函数: set_chunk_time_interval (无法获取函数定义)

-- 函数: set_integer_now_func (无法获取函数定义)

-- 函数: set_number_partitions (无法获取函数定义)

-- 函数: set_partitioning_interval (无法获取函数定义)

-- 函数: show_chunks (无法获取函数定义)

-- 函数: show_tablespaces (无法获取函数定义)

-- 函数: split_chunk (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket (无法获取函数定义)

-- 函数: time_bucket_gapfill (无法获取函数定义)

-- 函数: time_bucket_gapfill (无法获取函数定义)

-- 函数: time_bucket_gapfill (无法获取函数定义)

-- 函数: time_bucket_gapfill (无法获取函数定义)

-- 函数: time_bucket_gapfill (无法获取函数定义)

-- 函数: time_bucket_gapfill (无法获取函数定义)

-- 函数: time_bucket_gapfill (无法获取函数定义)

-- 函数: timescaledb_post_restore (无法获取函数定义)

-- 函数: timescaledb_pre_restore (无法获取函数定义)

-- 函数: to_uuidv7 (无法获取函数定义)

-- 函数: to_uuidv7_boundary (无法获取函数定义)

-- 函数: update_ohlcv_market_cap (无法获取函数定义)

-- 函数: uuid_timestamp (无法获取函数定义)

-- 函数: uuid_timestamp_micros (无法获取函数定义)

-- 函数: uuid_version (无法获取函数定义)


-- === 其他约束 ===
-- 约束: indecator_bull_bear_phase_check (表: indecator_bull_bear)
ALTER TABLE public.indecator_bull_bear ADD CHECK (((phase)::text = ANY (ARRAY[('Bull'::character varying)::text, ('Bear'::character varying)::text, ('Neutral'::character varying)::text])));


-- DDL导出完成
