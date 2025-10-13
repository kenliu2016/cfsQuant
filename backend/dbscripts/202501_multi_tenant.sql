-- Multi-tenant enablement migration
-- This script introduces tenant isolation primitives and retrofits
-- existing tables with a tenant discriminator column.

BEGIN;

CREATE TABLE IF NOT EXISTS public.tenants (
    tenant_id varchar PRIMARY KEY,
    name varchar NOT NULL,
    description text,
    is_active boolean DEFAULT TRUE,
    settings jsonb DEFAULT '{}'::jsonb,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

INSERT INTO public.tenants (tenant_id, name, description)
VALUES ('public', 'Default Tenant', 'System default tenant')
ON CONFLICT (tenant_id) DO NOTHING;

-- Helper function to add tenant column safely
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN SELECT unnest(ARRAY[
        'sys_strategies',
        'tuning_tasks',
        'tuning_results',
        'backtest_runs',
        'backtest_trades',
        'backtest_equity_curve',
        'backtest_grid_levels',
        'backtest_metrics',
        'backtest_orders',
        'backtest_positions',
        'backtest_reports',
        'market_codes'
    ]) LOOP
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS tenant_id varchar DEFAULT ''public''', tbl);
        EXECUTE format('UPDATE public.%I SET tenant_id = ''public'' WHERE tenant_id IS NULL', tbl);
        EXECUTE format('ALTER TABLE public.%I ALTER COLUMN tenant_id SET NOT NULL', tbl);
        EXECUTE format('ALTER TABLE public.%I ALTER COLUMN tenant_id DROP DEFAULT', tbl);
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS public.tenant_exchange_accounts (
    id uuid PRIMARY KEY,
    tenant_id varchar NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    exchange varchar NOT NULL,
    label varchar,
    api_key varchar NOT NULL,
    api_secret varchar NOT NULL,
    api_passphrase varchar,
    extra jsonb DEFAULT '{}'::jsonb,
    is_active boolean DEFAULT TRUE,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tenant_users (
    id uuid PRIMARY KEY,
    tenant_id varchar NOT NULL REFERENCES public.tenants(tenant_id) ON DELETE CASCADE,
    email varchar NOT NULL,
    hashed_password varchar NOT NULL,
    full_name varchar,
    is_admin boolean DEFAULT FALSE,
    is_active boolean DEFAULT TRUE,
    created_at timestamp DEFAULT now(),
    updated_at timestamp DEFAULT now(),
    UNIQUE(tenant_id, email)
);

INSERT INTO public.tenant_users (id, tenant_id, email, hashed_password, full_name, is_admin, is_active, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'public',
    'admin@local',
    '$2b$12$DfJXwyMRaQlWcVjmSY3F5eQlf96hosAQ/14IZQMi18RnBvRU6YYD.',
    'System Admin',
    TRUE,
    TRUE,
    NOW(),
    NOW()
)
ON CONFLICT (tenant_id, email) DO NOTHING;

-- Adjust constraints for tenant scope
ALTER TABLE public.sys_strategies
    DROP CONSTRAINT IF EXISTS sys_strategies_name_key;
ALTER TABLE public.sys_strategies
    ADD CONSTRAINT sys_strategies_name_key UNIQUE (tenant_id, name);

ALTER TABLE public.market_codes
    DROP CONSTRAINT IF EXISTS market_codes_pkey;
ALTER TABLE public.market_codes
    ADD CONSTRAINT market_codes_pkey PRIMARY KEY (tenant_id, exchange, code);

ALTER TABLE public.tuning_tasks
    DROP CONSTRAINT IF EXISTS tuning_tasks_pkey;
ALTER TABLE public.tuning_tasks
    ADD CONSTRAINT tuning_tasks_pkey PRIMARY KEY (tenant_id, task_id);

ALTER TABLE public.tuning_results
    DROP CONSTRAINT IF EXISTS tuning_results_pkey;
ALTER TABLE public.tuning_results
    ADD CONSTRAINT tuning_results_pkey PRIMARY KEY (tenant_id, run_id, task_id);

-- Ensure foreign keys remain valid after widening primary keys
ALTER TABLE public.tuning_results
    DROP CONSTRAINT IF EXISTS tuning_results_task_id_fkey;
ALTER TABLE public.tuning_results
    ADD CONSTRAINT tuning_results_task_id_fkey
    FOREIGN KEY (tenant_id, task_id) REFERENCES public.tuning_tasks(tenant_id, task_id) ON DELETE CASCADE;

-- Add supporting indexes for tenant-scoped queries
CREATE INDEX IF NOT EXISTS idx_backtest_runs_tenant_created_at
    ON public.backtest_runs (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_tenant_strategy
    ON public.backtest_runs (tenant_id, strategy, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_tenant_run
    ON public.backtest_trades (tenant_id, run_id, datetime);

CREATE INDEX IF NOT EXISTS idx_backtest_equity_curve_tenant_run
    ON public.backtest_equity_curve (tenant_id, run_id, datetime);

CREATE INDEX IF NOT EXISTS idx_backtest_grid_levels_tenant_run
    ON public.backtest_grid_levels (tenant_id, run_id);

CREATE INDEX IF NOT EXISTS idx_backtest_metrics_tenant_run
    ON public.backtest_metrics (tenant_id, run_id, metric_name);

CREATE INDEX IF NOT EXISTS idx_tuning_tasks_tenant_status
    ON public.tuning_tasks (tenant_id, status, created_at);

CREATE INDEX IF NOT EXISTS idx_tuning_results_tenant_task
    ON public.tuning_results (tenant_id, task_id, created_at);

CREATE INDEX IF NOT EXISTS idx_market_codes_tenant_exchange
    ON public.market_codes (tenant_id, exchange, watch, active);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tenant_exchange_accounts_unique
    ON public.tenant_exchange_accounts (tenant_id, exchange, COALESCE(label, 'default'));

CREATE INDEX IF NOT EXISTS idx_tenant_exchange_accounts_active
    ON public.tenant_exchange_accounts (tenant_id, is_active);

CREATE INDEX IF NOT EXISTS idx_tenant_users_active
    ON public.tenant_users (tenant_id, is_active);

COMMIT;
