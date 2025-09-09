-- 向runs表添加paras字段，用于存储执行策略时的参数
alter table public.runs
add column if not exists paras jsonb default '{}'::jsonb;

-- 为新添加的paras字段添加注释
comment on column public.runs.paras is '执行策略时的参数，以JSON格式存储';