-- 数据库DDL导出
-- 数据库: quant
-- 主机: localhost:5432
-- 导出时间: 2025-10-13 17:01:39
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
-- 未找到需要导出的数据库扩展


-- === 序列 ===
-- 序列: cron_log_id_seq
CREATE SEQUENCE IF NOT EXISTS public.cron_log_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_fear_greed_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_fear_greed_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_hmm_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_hmm_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_metrics_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_metrics_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: indecator_vmr_id_seq
CREATE SEQUENCE IF NOT EXISTS public.indecator_vmr_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;

-- 序列: sys_strategies_id_seq
CREATE SEQUENCE IF NOT EXISTS public.sys_strategies_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;


-- === 表结构 ===
-- 表: backtest_equity_curve
CREATE TABLE IF NOT EXISTS public.backtest_equity_curve (
    run_id text,
    datetime timestamp,
    nav float8,
    drawdown float8
);

-- 表: backtest_grid_levels
CREATE TABLE IF NOT EXISTS public.backtest_grid_levels (
    run_id text,
    level int8,
    price float8,
    name text
);

-- 表: backtest_metrics
CREATE TABLE IF NOT EXISTS public.backtest_metrics (
    run_id varchar NOT NULL,
    metric_name varchar NOT NULL,
    metric_value float8,
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
    reason varchar
);

-- 表: backtest_positions
CREATE TABLE IF NOT EXISTS public.backtest_positions (
    run_id varchar,
    datetime timestamp,
    code varchar,
    qty float8,
    avg_price float8
);

-- 表: backtest_reports
CREATE TABLE IF NOT EXISTS public.backtest_reports (
    run_id varchar NOT NULL,
    report_path varchar,
    artifact_paths jsonb,
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
    current_cash numeric
);
COMMENT ON COLUMN public.backtest_trades.nav IS '交易时的净资产价值(Net Asset Value)';
COMMENT ON COLUMN public.backtest_trades.trade_type IS '记录交易类型，如 ''normal'', ''take_profit'', ''stop_loss'' 等';
COMMENT ON COLUMN public.backtest_trades.drawdown IS '交易时的回撤比例';
COMMENT ON COLUMN public.backtest_trades.current_qty IS '交易后的数量';
COMMENT ON COLUMN public.backtest_trades.current_avg_price IS '交易后的平均价格';
COMMENT ON COLUMN public.backtest_trades.current_cash IS '交易后的现金余额';

-- 表: indecator_fear_greed
CREATE TABLE IF NOT EXISTS public.indecator_fear_greed (
    id int4 NOT NULL,
    timestamp timestamp NOT NULL,
    value numeric NOT NULL,
    value_classification varchar NOT NULL,
    source varchar DEFAULT 'CMC'::character varying,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE ("timestamp")
);

-- 表: indecator_hmm
CREATE TABLE IF NOT EXISTS public.indecator_hmm (
    id int4 NOT NULL,
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    timeframe varchar NOT NULL,
    datetime timestamp NOT NULL,
    state_prob_0 numeric NOT NULL,
    state_prob_1 numeric NOT NULL,
    signal varchar NOT NULL,
    position numeric NOT NULL,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (exchange, code, timeframe, datetime)
);

-- 表: indecator_metrics
CREATE TABLE IF NOT EXISTS public.indecator_metrics (
    id int4 NOT NULL,
    exchange varchar NOT NULL,
    symbol varchar NOT NULL,
    datetime timestamp NOT NULL DEFAULT now(),
    funding_rate numeric,
    stablecoin_flow numeric,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);

-- 表: indecator_vmr
CREATE TABLE IF NOT EXISTS public.indecator_vmr (
    id int4 NOT NULL,
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    timeframe varchar NOT NULL,
    datetime timestamp NOT NULL,
    window_hours int4 NOT NULL,
    vmr numeric,
    threshold numeric,
    is_active bool,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);

-- 表: market_codes
CREATE TABLE IF NOT EXISTS public.market_codes (
    exchange text NOT NULL,
    code text NOT NULL,
    active bool NOT NULL DEFAULT true,
    excode text NOT NULL DEFAULT 1,
    watch bool NOT NULL DEFAULT false,
    PRIMARY KEY (exchange, code)
);

-- 表: market_day_klines_2022
CREATE TABLE IF NOT EXISTS public.market_day_klines_2022 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime date NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_day_klines_2023
CREATE TABLE IF NOT EXISTS public.market_day_klines_2023 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime date NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_day_klines_2024
CREATE TABLE IF NOT EXISTS public.market_day_klines_2024 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime date NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_day_klines_2025
CREATE TABLE IF NOT EXISTS public.market_day_klines_2025 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime date NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2022_09
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2022_09 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2022_10
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2022_10 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2022_11
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2022_11 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2022_12
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2022_12 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_01
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_01 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_02
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_02 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_03
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_03 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_04
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_04 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_05
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_05 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_06
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_06 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_07
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_07 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_08
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_08 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_09
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_09 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_10
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_10 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_11
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_11 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2023_12
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2023_12 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_01
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_01 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_02
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_02 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_03
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_03 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_04
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_04 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_05
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_05 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_06
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_06 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_07
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_07 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_08
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_08 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_09
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_09 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_10
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_10 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_11
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_11 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2024_12
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2024_12 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_01
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_01 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_02
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_02 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_03
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_03 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_04
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_04 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_05
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_05 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_06
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_06 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_07
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_07 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_08
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_08 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_09
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_09 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_10
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_10 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_11
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_11 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_hour_klines_2025_12
CREATE TABLE IF NOT EXISTS public.market_hour_klines_2025_12 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2022_09
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2022_09 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2022_10
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2022_10 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2022_11
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2022_11 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2022_12
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2022_12 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_01
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_01 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_02
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_02 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_03
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_03 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_04
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_04 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_05
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_05 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_06
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_06 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_07
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_07 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_08
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_08 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_09
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_09 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_10
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_10 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_11
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_11 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2023_12
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2023_12 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_01
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_01 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_02
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_02 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_03
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_03 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_04
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_04 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_05
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_05 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_06
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_06 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_07
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_07 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_08
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_08 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_09
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_09 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_10
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_10 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_11
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_11 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2024_12
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2024_12 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_01
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_01 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_02
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_02 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_03
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_03 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_04
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_04 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_05
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_05 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_06
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_06 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_07
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_07 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_08
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_08 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_09
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_09 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_10
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_10 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_11
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_11 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
);

-- 表: market_minute_klines_2025_12
CREATE TABLE IF NOT EXISTS public.market_minute_klines_2025_12 (
    exchange varchar NOT NULL,
    code varchar NOT NULL,
    datetime timestamp NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric NOT NULL,
    raw jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    PRIMARY KEY (exchange, code, datetime)
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
    PRIMARY KEY (id),
    UNIQUE (name)
);

-- 表: tuning_results
CREATE TABLE IF NOT EXISTS public.tuning_results (
    task_id varchar NOT NULL,
    run_id varchar NOT NULL,
    params jsonb,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (run_id, task_id)
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
    PRIMARY KEY (task_id)
);


-- === 视图 ===
-- 视图: market_records_count
CREATE OR REPLACE VIEW public.market_records_count AS
 WITH minute_counts AS (
         SELECT market_minute_klines.exchange,
            market_minute_klines.code,
            count(*) AS minute_count
           FROM market_minute_klines
          GROUP BY market_minute_klines.exchange, market_minute_klines.code
        ), hour_counts AS (
         SELECT market_hour_klines.exchange,
            market_hour_klines.code,
            count(*) AS hour_count
           FROM market_hour_klines
          GROUP BY market_hour_klines.exchange, market_hour_klines.code
        ), day_counts AS (
         SELECT market_day_klines.exchange,
            market_day_klines.code,
            count(*) AS day_count
           FROM market_day_klines
          GROUP BY market_day_klines.exchange, market_day_klines.code
        ), all_exchanges_codes AS (
         SELECT DISTINCT market_codes.exchange,
            market_codes.excode AS code
           FROM market_codes
        UNION
         SELECT DISTINCT market_minute_klines.exchange,
            market_minute_klines.code
           FROM market_minute_klines
        UNION
         SELECT DISTINCT market_hour_klines.exchange,
            market_hour_klines.code
           FROM market_hour_klines
        UNION
         SELECT DISTINCT market_day_klines.exchange,
            market_day_klines.code
           FROM market_day_klines
        )
 SELECT a.exchange,
    a.code,
    COALESCE(m.minute_count, 0::bigint) AS minute_count,
    COALESCE(h.hour_count, 0::bigint) AS hour_count,
    COALESCE(d.day_count, 0::bigint) AS day_count,
    COALESCE(m.minute_count, 0::bigint) + COALESCE(h.hour_count, 0::bigint) + COALESCE(d.day_count, 0::bigint) AS total_count
   FROM all_exchanges_codes a
     LEFT JOIN minute_counts m ON a.exchange = m.exchange::text AND a.code = m.code::text
     LEFT JOIN hour_counts h ON a.exchange = h.exchange::text AND a.code = h.code::text
     LEFT JOIN day_counts d ON a.exchange = d.exchange::text AND a.code = d.code::text
  ORDER BY a.exchange, a.code;;


-- === 索引 ===
-- 索引: idx_backtest_metrics_run (表: backtest_metrics)
CREATE INDEX idx_backtest_metrics_run ON public.backtest_metrics USING btree (run_id);

-- 索引: idx_runs_code (表: backtest_runs)
CREATE INDEX idx_runs_code ON public.backtest_runs USING btree (code);

-- 索引: idx_runs_strategy (表: backtest_runs)
CREATE INDEX idx_runs_strategy ON public.backtest_runs USING btree (strategy);

-- 索引: indecator_metrics_idx (表: indecator_metrics)
CREATE INDEX indecator_metrics_idx ON public.indecator_metrics USING btree (exchange, symbol, datetime);

-- 索引: idx_vmr_metrics_code_timeframe_datetime (表: indecator_vmr)
CREATE INDEX idx_vmr_metrics_code_timeframe_datetime ON public.indecator_vmr USING btree (code, timeframe, datetime);

-- 索引: idx_market_day_klines_2022_exchange_code_datetime (表: market_day_klines_2022)
CREATE INDEX idx_market_day_klines_2022_exchange_code_datetime ON public.market_day_klines_2022 USING btree (exchange, code, datetime);

-- 索引: idx_market_day_klines_2023_exchange_code_datetime (表: market_day_klines_2023)
CREATE INDEX idx_market_day_klines_2023_exchange_code_datetime ON public.market_day_klines_2023 USING btree (exchange, code, datetime);

-- 索引: idx_market_day_klines_2024_exchange_code_datetime (表: market_day_klines_2024)
CREATE INDEX idx_market_day_klines_2024_exchange_code_datetime ON public.market_day_klines_2024 USING btree (exchange, code, datetime);

-- 索引: idx_market_day_klines_2025_exchange_code_datetime (表: market_day_klines_2025)
CREATE INDEX idx_market_day_klines_2025_exchange_code_datetime ON public.market_day_klines_2025 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2022_09_exchange_code_datetime (表: market_hour_klines_2022_09)
CREATE INDEX idx_market_hour_klines_2022_09_exchange_code_datetime ON public.market_hour_klines_2022_09 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2022_10_exchange_code_datetime (表: market_hour_klines_2022_10)
CREATE INDEX idx_market_hour_klines_2022_10_exchange_code_datetime ON public.market_hour_klines_2022_10 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2022_11_exchange_code_datetime (表: market_hour_klines_2022_11)
CREATE INDEX idx_market_hour_klines_2022_11_exchange_code_datetime ON public.market_hour_klines_2022_11 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2022_12_exchange_code_datetime (表: market_hour_klines_2022_12)
CREATE INDEX idx_market_hour_klines_2022_12_exchange_code_datetime ON public.market_hour_klines_2022_12 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_01_exchange_code_datetime (表: market_hour_klines_2023_01)
CREATE INDEX idx_market_hour_klines_2023_01_exchange_code_datetime ON public.market_hour_klines_2023_01 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_02_exchange_code_datetime (表: market_hour_klines_2023_02)
CREATE INDEX idx_market_hour_klines_2023_02_exchange_code_datetime ON public.market_hour_klines_2023_02 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_03_exchange_code_datetime (表: market_hour_klines_2023_03)
CREATE INDEX idx_market_hour_klines_2023_03_exchange_code_datetime ON public.market_hour_klines_2023_03 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_04_exchange_code_datetime (表: market_hour_klines_2023_04)
CREATE INDEX idx_market_hour_klines_2023_04_exchange_code_datetime ON public.market_hour_klines_2023_04 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_05_exchange_code_datetime (表: market_hour_klines_2023_05)
CREATE INDEX idx_market_hour_klines_2023_05_exchange_code_datetime ON public.market_hour_klines_2023_05 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_06_exchange_code_datetime (表: market_hour_klines_2023_06)
CREATE INDEX idx_market_hour_klines_2023_06_exchange_code_datetime ON public.market_hour_klines_2023_06 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_07_exchange_code_datetime (表: market_hour_klines_2023_07)
CREATE INDEX idx_market_hour_klines_2023_07_exchange_code_datetime ON public.market_hour_klines_2023_07 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_08_exchange_code_datetime (表: market_hour_klines_2023_08)
CREATE INDEX idx_market_hour_klines_2023_08_exchange_code_datetime ON public.market_hour_klines_2023_08 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_09_exchange_code_datetime (表: market_hour_klines_2023_09)
CREATE INDEX idx_market_hour_klines_2023_09_exchange_code_datetime ON public.market_hour_klines_2023_09 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_10_exchange_code_datetime (表: market_hour_klines_2023_10)
CREATE INDEX idx_market_hour_klines_2023_10_exchange_code_datetime ON public.market_hour_klines_2023_10 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_11_exchange_code_datetime (表: market_hour_klines_2023_11)
CREATE INDEX idx_market_hour_klines_2023_11_exchange_code_datetime ON public.market_hour_klines_2023_11 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2023_12_exchange_code_datetime (表: market_hour_klines_2023_12)
CREATE INDEX idx_market_hour_klines_2023_12_exchange_code_datetime ON public.market_hour_klines_2023_12 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_01_exchange_code_datetime (表: market_hour_klines_2024_01)
CREATE INDEX idx_market_hour_klines_2024_01_exchange_code_datetime ON public.market_hour_klines_2024_01 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_02_exchange_code_datetime (表: market_hour_klines_2024_02)
CREATE INDEX idx_market_hour_klines_2024_02_exchange_code_datetime ON public.market_hour_klines_2024_02 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_03_exchange_code_datetime (表: market_hour_klines_2024_03)
CREATE INDEX idx_market_hour_klines_2024_03_exchange_code_datetime ON public.market_hour_klines_2024_03 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_04_exchange_code_datetime (表: market_hour_klines_2024_04)
CREATE INDEX idx_market_hour_klines_2024_04_exchange_code_datetime ON public.market_hour_klines_2024_04 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_05_exchange_code_datetime (表: market_hour_klines_2024_05)
CREATE INDEX idx_market_hour_klines_2024_05_exchange_code_datetime ON public.market_hour_klines_2024_05 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_06_exchange_code_datetime (表: market_hour_klines_2024_06)
CREATE INDEX idx_market_hour_klines_2024_06_exchange_code_datetime ON public.market_hour_klines_2024_06 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_07_exchange_code_datetime (表: market_hour_klines_2024_07)
CREATE INDEX idx_market_hour_klines_2024_07_exchange_code_datetime ON public.market_hour_klines_2024_07 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_08_exchange_code_datetime (表: market_hour_klines_2024_08)
CREATE INDEX idx_market_hour_klines_2024_08_exchange_code_datetime ON public.market_hour_klines_2024_08 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_09_exchange_code_datetime (表: market_hour_klines_2024_09)
CREATE INDEX idx_market_hour_klines_2024_09_exchange_code_datetime ON public.market_hour_klines_2024_09 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_10_exchange_code_datetime (表: market_hour_klines_2024_10)
CREATE INDEX idx_market_hour_klines_2024_10_exchange_code_datetime ON public.market_hour_klines_2024_10 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_11_exchange_code_datetime (表: market_hour_klines_2024_11)
CREATE INDEX idx_market_hour_klines_2024_11_exchange_code_datetime ON public.market_hour_klines_2024_11 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2024_12_exchange_code_datetime (表: market_hour_klines_2024_12)
CREATE INDEX idx_market_hour_klines_2024_12_exchange_code_datetime ON public.market_hour_klines_2024_12 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_01_exchange_code_datetime (表: market_hour_klines_2025_01)
CREATE INDEX idx_market_hour_klines_2025_01_exchange_code_datetime ON public.market_hour_klines_2025_01 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_02_exchange_code_datetime (表: market_hour_klines_2025_02)
CREATE INDEX idx_market_hour_klines_2025_02_exchange_code_datetime ON public.market_hour_klines_2025_02 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_03_exchange_code_datetime (表: market_hour_klines_2025_03)
CREATE INDEX idx_market_hour_klines_2025_03_exchange_code_datetime ON public.market_hour_klines_2025_03 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_04_exchange_code_datetime (表: market_hour_klines_2025_04)
CREATE INDEX idx_market_hour_klines_2025_04_exchange_code_datetime ON public.market_hour_klines_2025_04 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_05_exchange_code_datetime (表: market_hour_klines_2025_05)
CREATE INDEX idx_market_hour_klines_2025_05_exchange_code_datetime ON public.market_hour_klines_2025_05 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_06_exchange_code_datetime (表: market_hour_klines_2025_06)
CREATE INDEX idx_market_hour_klines_2025_06_exchange_code_datetime ON public.market_hour_klines_2025_06 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_07_exchange_code_datetime (表: market_hour_klines_2025_07)
CREATE INDEX idx_market_hour_klines_2025_07_exchange_code_datetime ON public.market_hour_klines_2025_07 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_08_exchange_code_datetime (表: market_hour_klines_2025_08)
CREATE INDEX idx_market_hour_klines_2025_08_exchange_code_datetime ON public.market_hour_klines_2025_08 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_09_exchange_code_datetime (表: market_hour_klines_2025_09)
CREATE INDEX idx_market_hour_klines_2025_09_exchange_code_datetime ON public.market_hour_klines_2025_09 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_10_exchange_code_datetime (表: market_hour_klines_2025_10)
CREATE INDEX idx_market_hour_klines_2025_10_exchange_code_datetime ON public.market_hour_klines_2025_10 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_11_exchange_code_datetime (表: market_hour_klines_2025_11)
CREATE INDEX idx_market_hour_klines_2025_11_exchange_code_datetime ON public.market_hour_klines_2025_11 USING btree (exchange, code, datetime);

-- 索引: idx_market_hour_klines_2025_12_exchange_code_datetime (表: market_hour_klines_2025_12)
CREATE INDEX idx_market_hour_klines_2025_12_exchange_code_datetime ON public.market_hour_klines_2025_12 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2022_09_exchange_code_datetime (表: market_minute_klines_2022_09)
CREATE INDEX idx_market_minute_klines_2022_09_exchange_code_datetime ON public.market_minute_klines_2022_09 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2022_10_exchange_code_datetime (表: market_minute_klines_2022_10)
CREATE INDEX idx_market_minute_klines_2022_10_exchange_code_datetime ON public.market_minute_klines_2022_10 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2022_11_exchange_code_datetime (表: market_minute_klines_2022_11)
CREATE INDEX idx_market_minute_klines_2022_11_exchange_code_datetime ON public.market_minute_klines_2022_11 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2022_12_exchange_code_datetime (表: market_minute_klines_2022_12)
CREATE INDEX idx_market_minute_klines_2022_12_exchange_code_datetime ON public.market_minute_klines_2022_12 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_01_exchange_code_datetime (表: market_minute_klines_2023_01)
CREATE INDEX idx_market_minute_klines_2023_01_exchange_code_datetime ON public.market_minute_klines_2023_01 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_02_exchange_code_datetime (表: market_minute_klines_2023_02)
CREATE INDEX idx_market_minute_klines_2023_02_exchange_code_datetime ON public.market_minute_klines_2023_02 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_03_exchange_code_datetime (表: market_minute_klines_2023_03)
CREATE INDEX idx_market_minute_klines_2023_03_exchange_code_datetime ON public.market_minute_klines_2023_03 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_04_exchange_code_datetime (表: market_minute_klines_2023_04)
CREATE INDEX idx_market_minute_klines_2023_04_exchange_code_datetime ON public.market_minute_klines_2023_04 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_05_exchange_code_datetime (表: market_minute_klines_2023_05)
CREATE INDEX idx_market_minute_klines_2023_05_exchange_code_datetime ON public.market_minute_klines_2023_05 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_06_exchange_code_datetime (表: market_minute_klines_2023_06)
CREATE INDEX idx_market_minute_klines_2023_06_exchange_code_datetime ON public.market_minute_klines_2023_06 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_07_exchange_code_datetime (表: market_minute_klines_2023_07)
CREATE INDEX idx_market_minute_klines_2023_07_exchange_code_datetime ON public.market_minute_klines_2023_07 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_08_exchange_code_datetime (表: market_minute_klines_2023_08)
CREATE INDEX idx_market_minute_klines_2023_08_exchange_code_datetime ON public.market_minute_klines_2023_08 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_09_exchange_code_datetime (表: market_minute_klines_2023_09)
CREATE INDEX idx_market_minute_klines_2023_09_exchange_code_datetime ON public.market_minute_klines_2023_09 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_10_exchange_code_datetime (表: market_minute_klines_2023_10)
CREATE INDEX idx_market_minute_klines_2023_10_exchange_code_datetime ON public.market_minute_klines_2023_10 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_11_exchange_code_datetime (表: market_minute_klines_2023_11)
CREATE INDEX idx_market_minute_klines_2023_11_exchange_code_datetime ON public.market_minute_klines_2023_11 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2023_12_exchange_code_datetime (表: market_minute_klines_2023_12)
CREATE INDEX idx_market_minute_klines_2023_12_exchange_code_datetime ON public.market_minute_klines_2023_12 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_01_exchange_code_datetime (表: market_minute_klines_2024_01)
CREATE INDEX idx_market_minute_klines_2024_01_exchange_code_datetime ON public.market_minute_klines_2024_01 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_02_exchange_code_datetime (表: market_minute_klines_2024_02)
CREATE INDEX idx_market_minute_klines_2024_02_exchange_code_datetime ON public.market_minute_klines_2024_02 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_03_exchange_code_datetime (表: market_minute_klines_2024_03)
CREATE INDEX idx_market_minute_klines_2024_03_exchange_code_datetime ON public.market_minute_klines_2024_03 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_04_exchange_code_datetime (表: market_minute_klines_2024_04)
CREATE INDEX idx_market_minute_klines_2024_04_exchange_code_datetime ON public.market_minute_klines_2024_04 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_05_exchange_code_datetime (表: market_minute_klines_2024_05)
CREATE INDEX idx_market_minute_klines_2024_05_exchange_code_datetime ON public.market_minute_klines_2024_05 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_06_exchange_code_datetime (表: market_minute_klines_2024_06)
CREATE INDEX idx_market_minute_klines_2024_06_exchange_code_datetime ON public.market_minute_klines_2024_06 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_07_exchange_code_datetime (表: market_minute_klines_2024_07)
CREATE INDEX idx_market_minute_klines_2024_07_exchange_code_datetime ON public.market_minute_klines_2024_07 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_08_exchange_code_datetime (表: market_minute_klines_2024_08)
CREATE INDEX idx_market_minute_klines_2024_08_exchange_code_datetime ON public.market_minute_klines_2024_08 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_09_exchange_code_datetime (表: market_minute_klines_2024_09)
CREATE INDEX idx_market_minute_klines_2024_09_exchange_code_datetime ON public.market_minute_klines_2024_09 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_10_exchange_code_datetime (表: market_minute_klines_2024_10)
CREATE INDEX idx_market_minute_klines_2024_10_exchange_code_datetime ON public.market_minute_klines_2024_10 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_11_exchange_code_datetime (表: market_minute_klines_2024_11)
CREATE INDEX idx_market_minute_klines_2024_11_exchange_code_datetime ON public.market_minute_klines_2024_11 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2024_12_exchange_code_datetime (表: market_minute_klines_2024_12)
CREATE INDEX idx_market_minute_klines_2024_12_exchange_code_datetime ON public.market_minute_klines_2024_12 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_01_exchange_code_datetime (表: market_minute_klines_2025_01)
CREATE INDEX idx_market_minute_klines_2025_01_exchange_code_datetime ON public.market_minute_klines_2025_01 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_02_exchange_code_datetime (表: market_minute_klines_2025_02)
CREATE INDEX idx_market_minute_klines_2025_02_exchange_code_datetime ON public.market_minute_klines_2025_02 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_03_exchange_code_datetime (表: market_minute_klines_2025_03)
CREATE INDEX idx_market_minute_klines_2025_03_exchange_code_datetime ON public.market_minute_klines_2025_03 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_04_exchange_code_datetime (表: market_minute_klines_2025_04)
CREATE INDEX idx_market_minute_klines_2025_04_exchange_code_datetime ON public.market_minute_klines_2025_04 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_05_exchange_code_datetime (表: market_minute_klines_2025_05)
CREATE INDEX idx_market_minute_klines_2025_05_exchange_code_datetime ON public.market_minute_klines_2025_05 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_06_exchange_code_datetime (表: market_minute_klines_2025_06)
CREATE INDEX idx_market_minute_klines_2025_06_exchange_code_datetime ON public.market_minute_klines_2025_06 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_07_exchange_code_datetime (表: market_minute_klines_2025_07)
CREATE INDEX idx_market_minute_klines_2025_07_exchange_code_datetime ON public.market_minute_klines_2025_07 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_08_exchange_code_datetime (表: market_minute_klines_2025_08)
CREATE INDEX idx_market_minute_klines_2025_08_exchange_code_datetime ON public.market_minute_klines_2025_08 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_09_exchange_code_datetime (表: market_minute_klines_2025_09)
CREATE INDEX idx_market_minute_klines_2025_09_exchange_code_datetime ON public.market_minute_klines_2025_09 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_10_exchange_code_datetime (表: market_minute_klines_2025_10)
CREATE INDEX idx_market_minute_klines_2025_10_exchange_code_datetime ON public.market_minute_klines_2025_10 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_11_exchange_code_datetime (表: market_minute_klines_2025_11)
CREATE INDEX idx_market_minute_klines_2025_11_exchange_code_datetime ON public.market_minute_klines_2025_11 USING btree (exchange, code, datetime);

-- 索引: idx_market_minute_klines_2025_12_exchange_code_datetime (表: market_minute_klines_2025_12)
CREATE INDEX idx_market_minute_klines_2025_12_exchange_code_datetime ON public.market_minute_klines_2025_12 USING btree (exchange, code, datetime);

-- 索引: idx_tuning_results_task (表: tuning_results)
CREATE INDEX idx_tuning_results_task ON public.tuning_results USING btree (task_id);

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

-- 索引: idx_tuning_tasks_timeout (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_timeout ON public.tuning_tasks USING btree (timeout);


-- === 触发器 ===
-- 未找到需要导出的数据库触发器


-- === 函数 ===
-- 未找到需要导出的数据库函数


-- === 其他约束 ===
-- 约束: metrics_run_id_fkey (表: backtest_metrics)
ALTER TABLE public.backtest_metrics ADD FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id) ON DELETE CASCADE;

-- 约束: orders_run_id_fkey (表: backtest_orders)
ALTER TABLE public.backtest_orders ADD FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id);

-- 约束: reports_run_id_fkey1 (表: backtest_reports)
ALTER TABLE public.backtest_reports ADD FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id);

-- 约束: trades_run_id_fkey (表: backtest_trades)
ALTER TABLE public.backtest_trades ADD FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id);

-- 约束: tuning_results_run_id_fkey (表: tuning_results)
ALTER TABLE public.tuning_results ADD FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id) ON DELETE CASCADE;

-- 约束: tuning_results_task_id_fkey (表: tuning_results)
ALTER TABLE public.tuning_results ADD FOREIGN KEY (task_id) REFERENCES tuning_tasks(task_id) ON DELETE CASCADE;


-- DDL导出完成
