-- 为trades表添加trade_type列的ALTER TABLE脚本
ALTER TABLE public.trades 
ADD COLUMN trade_type VARCHAR(20) NOT NULL DEFAULT 'normal';

-- 可选：如果需要将新列放在特定位置（例如side列之后），可以使用以下语句
-- 注意：PostgreSQL不支持直接指定列的位置，但可以通过重建表来实现
-- 以下是替代方案，如果需要重新排序列
/*
BEGIN;

-- 创建新表并重新排列列
CREATE TABLE public.trades_new (
    run_id varchar NOT NULL,
    datetime TIMESTAMP NOT NULL,
    code VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,          -- 'buy' 或 'sell'
    trade_type VARCHAR(20) NOT NULL DEFAULT 'normal', -- 新增：记录交易类型
    price NUMERIC(18,8) NOT NULL,      -- 成交价
    qty NUMERIC(18,8) NOT NULL,        -- 数量
    amount NUMERIC(18,8) NOT NULL,     -- 成交额
    fee NUMERIC(18,8) NOT NULL,        -- 手续费
    avg_price NUMERIC(18,8),           -- 持仓均价
    nav NUMERIC(18,8),                 -- 交易时净值
    realized_pnl NUMERIC(18,8),        -- 已实现盈亏（卖出时）
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

-- 复制数据到新表
INSERT INTO public.trades_new 
SELECT run_id, datetime, code, side, 'normal', price, qty, amount, fee, avg_price, nav, realized_pnl, created_at 
FROM public.trades;

-- 删除旧表
DROP TABLE public.trades;

-- 重命名新表
ALTER TABLE public.trades_new RENAME TO trades;

COMMIT;
*/

-- 添加注释说明新列的用途
COMMENT ON COLUMN public.trades.trade_type IS '记录交易类型，如 ''normal'', ''take_profit'', ''stop_loss'' 等';