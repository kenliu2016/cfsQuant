-- 数据库DDL导出
-- 数据库: quant
-- 主机: localhost:5432
-- 导出时间: 2025-09-27 05:21:19
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

-- 序列: strategies_id_seq
CREATE SEQUENCE IF NOT EXISTS public.strategies_id_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 NO CYCLE;


-- === 表结构 ===
-- 表: cron_log
CREATE TABLE IF NOT EXISTS public.cron_log (
    id int4 NOT NULL,
    job_name text,
    status text,
    message text,
    started_at timestamp,
    ended_at timestamp,
    PRIMARY KEY (id)
);


-- 表: equity_curve
CREATE TABLE IF NOT EXISTS public.equity_curve (
    run_id text,
    datetime timestamp,
    nav float8,
    drawdown float8
);

-- 表: grid_levels
CREATE TABLE IF NOT EXISTS public.grid_levels (
    run_id text,
    level int8,
    price float8,
    name text
);


-- 表: metrics
CREATE TABLE IF NOT EXISTS public.metrics (
    run_id varchar NOT NULL,
    metric_name varchar NOT NULL,
    metric_value float8,
    PRIMARY KEY (run_id, metric_name)
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
COMMENT ON COLUMN public.runs.paras IS '执行策略时的参数，以JSON格式存储';
COMMENT ON COLUMN public.runs.win_rate IS '胜率 - 盈利交易占总交易的比例';
COMMENT ON COLUMN public.runs.trade_count IS '交易次数 - 总交易笔数';
COMMENT ON COLUMN public.runs.total_fee IS '总手续费 - 所有交易的手续费总和';
COMMENT ON COLUMN public.runs.total_profit IS '总收益 - 所有交易的盈亏总和';

-- 表: strategies
CREATE TABLE IF NOT EXISTS public.strategies (
    id int4 NOT NULL,
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
    trade_type varchar NOT NULL DEFAULT 'normal'::character varying,
    drawdown float8,
    current_qty numeric,
    current_avg_price numeric,
    close_price numeric,
    current_cash numeric
);
COMMENT ON COLUMN public.trades.nav IS '交易时的净资产价值(Net Asset Value)';
COMMENT ON COLUMN public.trades.trade_type IS '记录交易类型，如 ''normal'', ''take_profit'', ''stop_loss'' 等';
COMMENT ON COLUMN public.trades.drawdown IS '交易时的回撤比例';
COMMENT ON COLUMN public.trades.current_qty IS '交易后的数量';
COMMENT ON COLUMN public.trades.current_avg_price IS '交易后的平均价格';
COMMENT ON COLUMN public.trades.current_cash IS '交易后的现金余额';

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
-- 未找到需要导出的数据库视图


-- === 索引 ===

-- 索引: idx_metrics_run (表: metrics)
CREATE INDEX idx_metrics_run ON public.metrics USING btree (run_id);

-- 索引: idx_runs_code (表: runs)
CREATE INDEX idx_runs_code ON public.runs USING btree (code);

-- 索引: idx_runs_strategy (表: runs)
CREATE INDEX idx_runs_strategy ON public.runs USING btree (strategy);

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
ALTER TABLE public.tuning_results ADD FOREIGN KEY (task_id) REFERENCES tuning_tasks(task_id) ON DELETE CASCADE;


-- DDL导出完成
