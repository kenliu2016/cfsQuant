CREATE TABLE IF NOT EXISTS public.minute_prediction (
  datetime timestamp without time zone NOT NULL,
  code varchar(32) NOT NULL,
  open double precision NOT NULL,
  high double precision NOT NULL,
  low double precision NOT NULL,
  close double precision NOT NULL,
  volume double precision NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_minute_prediction_code_time ON public.minute_prediction (code, datetime);

CREATE TABLE IF NOT EXISTS public.runs (
  run_id varchar(64) PRIMARY KEY,
  strategy varchar(128) NOT NULL,
  code varchar(32) NOT NULL,
  start_time timestamp without time zone NOT NULL,
  end_time timestamp without time zone NOT NULL,
  initial_capital double precision NOT NULL,
  final_capital double precision NOT NULL,
  created_at timestamp without time zone DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_runs_code ON public.runs (code);
CREATE INDEX IF NOT EXISTS idx_runs_strategy ON public.runs (strategy);
CREATE TABLE IF NOT EXISTS public.metrics (
  run_id varchar(64) NOT NULL,
  metric_name varchar(64) NOT NULL,
  metric_value double precision NOT NULL,
  CONSTRAINT metrics_run_id_fkey FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_metrics_run ON public.metrics (run_id);
-- 注意：equity表已被equity_curve表全面取代，保留此定义仅为历史兼容性
CREATE TABLE IF NOT EXISTS public.equity (
  run_id varchar(64) NOT NULL,
  datetime timestamp without time zone NOT NULL,
  nav double precision NOT NULL,
  drawdown double precision NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_equity_run ON public.equity (run_id);

-- equity_curve表全面取代equity表
CREATE TABLE IF NOT EXISTS public.equity_curve (
  run_id varchar(64) NOT NULL,
  datetime timestamp without time zone NOT NULL,
  nav double precision NOT NULL,
  drawdown double precision NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_equity_curve_run ON public.equity_curve (run_id);
CREATE TABLE IF NOT EXISTS public.trades (
  run_id varchar(64) NOT NULL,
  datetime timestamp without time zone NOT NULL,
  code varchar(32) NOT NULL,
  side varchar(8) NOT NULL,
  price double precision NOT NULL,
  qty double precision NOT NULL,
  amount double precision NOT NULL,
  fee double precision NOT NULL,
  CONSTRAINT trades_run_id_fkey FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_trades_run ON public.trades (run_id);

-- 确保tuning_results表的外键约束正确
-- CREATE TABLE IF NOT EXISTS public.tuning_results (
--   id serial PRIMARY KEY,
--   run_id varchar(64) NOT NULL,
--   -- 其他字段...
--   CONSTRAINT tuning_results_run_id_fkey FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
-- );