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
  start timestamp without time zone NOT NULL,
  end timestamp without time zone NOT NULL,
  initial_capital double precision NOT NULL,
  final_capital double precision NOT NULL,
  created_at timestamp without time zone DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS public.metrics (
  run_id varchar(64) NOT NULL,
  metric_name varchar(64) NOT NULL,
  metric_value double precision NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_run ON public.metrics (run_id);
CREATE TABLE IF NOT EXISTS public.equity (
  run_id varchar(64) NOT NULL,
  datetime timestamp without time zone NOT NULL,
  nav double precision NOT NULL,
  drawdown double precision NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_equity_run ON public.equity (run_id);
CREATE TABLE IF NOT EXISTS public.trades (
  run_id varchar(64) NOT NULL,
  datetime timestamp without time zone NOT NULL,
  code varchar(32) NOT NULL,
  side varchar(8) NOT NULL,
  price double precision NOT NULL,
  qty double precision NOT NULL,
  amount double precision NOT NULL,
  fee double precision NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_run ON public.trades (run_id);