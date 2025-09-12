-- 数据库DDL导出
-- 数据库: quant
-- 主机: localhost:5432
-- 导出时间: 2025-09-13 03:56:06
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

-- === 表结构 ===
-- 表: day_prediction
CREATE TABLE IF NOT EXISTS public.day_prediction (
    datetime timestamp NOT NULL,
    code varchar NOT NULL,
    open float8 NOT NULL,
    high float8 NOT NULL,
    low float8 NOT NULL,
    close float8 NOT NULL,
    volume float8 NOT NULL,
    UNIQUE (datetime, code)
);

-- 表: day_realtime
CREATE TABLE IF NOT EXISTS public.day_realtime (
    datetime timestamp NOT NULL,
    code varchar NOT NULL,
    open float8 NOT NULL,
    high float8 NOT NULL,
    low float8 NOT NULL,
    close float8 NOT NULL,
    volume float8 NOT NULL,
    UNIQUE (datetime, code)
);

-- 表: equity_curve
CREATE TABLE IF NOT EXISTS public.equity_curve (
    run_id text,
    datetime timestamp,
    nav float8,
    drawdown float8
);

-- 表: fills
CREATE TABLE IF NOT EXISTS public.fills (
    run_id varchar,
    datetime timestamp,
    code varchar,
    side varchar,
    qty float8,
    price float8,
    fee float8
);

-- 表: metrics
CREATE TABLE IF NOT EXISTS public.metrics (
    run_id varchar NOT NULL,
    metric_name varchar NOT NULL,
    metric_value float8,
    PRIMARY KEY (run_id, metric_name)
);

-- 表: minute_prediction
CREATE TABLE IF NOT EXISTS public.minute_prediction (
    datetime timestamp NOT NULL,
    code varchar NOT NULL,
    open float8 NOT NULL,
    high float8 NOT NULL,
    low float8 NOT NULL,
    close float8 NOT NULL,
    volume float8 NOT NULL,
    UNIQUE (datetime, code)
);

-- 表: minute_realtime
CREATE TABLE IF NOT EXISTS public.minute_realtime (
    datetime timestamp NOT NULL,
    code varchar NOT NULL,
    open float8 NOT NULL,
    high float8 NOT NULL,
    low float8 NOT NULL,
    close float8 NOT NULL,
    volume float8 NOT NULL,
    PRIMARY KEY (datetime, code),
    UNIQUE (datetime, code)
);

-- 表: notify_config
CREATE TABLE IF NOT EXISTS public.notify_config (
    id int4 NOT NULL DEFAULT nextval('notify_config_id_seq'::regclass),
    type varchar DEFAULT 'none'::character varying,
    config jsonb,
    PRIMARY KEY (id)
);

-- 表: orders
CREATE TABLE IF NOT EXISTS public.orders (
    run_id varchar,
    datetime timestamp,
    code varchar,
    side varchar,
    qty float8,
    price float8,
    reason varchar
);

-- 表: pine_webhook_log
CREATE TABLE IF NOT EXISTS public.pine_webhook_log (
    id int8 NOT NULL DEFAULT nextval('pine_webhook_log_id_seq'::regclass),
    received_at timestamp DEFAULT now(),
    payload jsonb,
    signature varchar,
    handled bool DEFAULT false,
    run_id uuid,
    PRIMARY KEY (id)
);

-- 表: positions
CREATE TABLE IF NOT EXISTS public.positions (
    run_id varchar,
    datetime timestamp,
    code varchar,
    qty float8,
    avg_price float8
);

-- 表: reports
CREATE TABLE IF NOT EXISTS public.reports (
    run_id varchar NOT NULL,
    report_path varchar,
    artifact_paths jsonb,
    PRIMARY KEY (run_id)
);

-- 表: runs
CREATE TABLE IF NOT EXISTS public.runs (
    strategy varchar NOT NULL,
    code varchar NOT NULL,
    start_time timestamp NOT NULL,
    end_time timestamp NOT NULL,
    initial_capital float8 NOT NULL,
    final_capital float8 NOT NULL,
    created_at timestamp DEFAULT now(),
    run_id varchar NOT NULL,
    paras jsonb DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id)
);
COMMENT ON COLUMN public.runs.paras IS '执行策略时的参数，以JSON格式存储';

-- 表: strategies
CREATE TABLE IF NOT EXISTS public.strategies (
    id int4 NOT NULL DEFAULT nextval('strategies_id_seq'::regclass),
    name text NOT NULL,
    description text,
    params jsonb DEFAULT '{}'::jsonb,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (name)
);

-- 表: trades
CREATE TABLE IF NOT EXISTS public.trades (
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
    trade_type varchar NOT NULL DEFAULT 'normal'::character varying
);
COMMENT ON COLUMN public.trades.trade_type IS '记录交易类型，如 ''normal'', ''take_profit'', ''stop_loss'' 等';

-- 表: tuning_results
CREATE TABLE IF NOT EXISTS public.tuning_results (
    id int4 NOT NULL DEFAULT nextval('tuning_results_id_seq'::regclass),
    task_id int4 NOT NULL,
    run_id varchar,
    params jsonb,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);

-- 表: tuning_tasks
CREATE TABLE IF NOT EXISTS public.tuning_tasks (
    id int4 NOT NULL DEFAULT nextval('tuning_tasks_id_seq'::regclass),
    strategy text,
    status text,
    total int4,
    finished int4,
    created_at timestamp DEFAULT now(),
    PRIMARY KEY (id)
);


-- === 视图 ===
-- 未找到需要导出的数据库视图


-- === 索引 ===
-- 索引: idx_day_prediction_code_time (表: day_prediction)
CREATE INDEX idx_day_prediction_code_time ON public.day_prediction USING btree (code, datetime);

-- 索引: idx_day_realtime_code_time (表: day_realtime)
CREATE INDEX idx_day_realtime_code_time ON public.day_realtime USING btree (code, datetime);

-- 索引: idx_day_realtime_datetime (表: day_realtime)
CREATE INDEX idx_day_realtime_datetime ON public.day_realtime USING btree (datetime);

-- 索引: idx_metrics_run (表: metrics)
CREATE INDEX idx_metrics_run ON public.metrics USING btree (run_id);

-- 索引: idx_minute_prediction_code_time (表: minute_prediction)
CREATE INDEX idx_minute_prediction_code_time ON public.minute_prediction USING btree (code, datetime);

-- 索引: idx_minute_realtime_code_time (表: minute_realtime)
CREATE INDEX idx_minute_realtime_code_time ON public.minute_realtime USING btree (code, datetime);

-- 索引: idx_minute_realtime_datetime (表: minute_realtime)
CREATE INDEX idx_minute_realtime_datetime ON public.minute_realtime USING btree (datetime);

-- 索引: idx_runs_code (表: runs)
CREATE INDEX idx_runs_code ON public.runs USING btree (code);

-- 索引: idx_runs_strategy (表: runs)
CREATE INDEX idx_runs_strategy ON public.runs USING btree (strategy);

-- 索引: idx_tuning_results_task (表: tuning_results)
CREATE INDEX idx_tuning_results_task ON public.tuning_results USING btree (task_id);

-- 索引: idx_tuning_tasks_status (表: tuning_tasks)
CREATE INDEX idx_tuning_tasks_status ON public.tuning_tasks USING btree (status);


-- === 触发器 ===
-- 未找到需要导出的数据库触发器


-- === 函数 ===

-- === 其他约束 ===
-- 约束: fills_run_id_fkey (表: fills)
ALTER TABLE public.fills ADD FOREIGN KEY (run_id) REFERENCES runs(run_id);

-- 约束: metrics_run_id_fkey (表: metrics)
ALTER TABLE public.metrics ADD FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE;

-- 约束: orders_run_id_fkey (表: orders)
ALTER TABLE public.orders ADD FOREIGN KEY (run_id) REFERENCES runs(run_id);

-- 约束: positions_run_id_fkey (表: positions)
ALTER TABLE public.positions ADD FOREIGN KEY (run_id) REFERENCES runs(run_id);

-- 约束: reports_run_id_fkey1 (表: reports)
ALTER TABLE public.reports ADD FOREIGN KEY (run_id) REFERENCES runs(run_id);

-- 约束: trades_run_id_fkey (表: trades)
ALTER TABLE public.trades ADD FOREIGN KEY (run_id) REFERENCES runs(run_id);

-- 约束: tuning_results_run_id_fkey (表: tuning_results)
ALTER TABLE public.tuning_results ADD FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE;

-- 约束: tuning_results_task_id_fkey (表: tuning_results)
ALTER TABLE public.tuning_results ADD FOREIGN KEY (task_id) REFERENCES tuning_tasks(id) ON DELETE CASCADE;


-- DDL导出完成
