-- 创建牛熊判定结果表
CREATE TABLE IF NOT EXISTS public.indecator_bull_bear (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    datetime TIMESTAMP NOT NULL DEFAULT now(),
    
    -- 判定结果
    score INTEGER NOT NULL,
    phase VARCHAR NOT NULL CHECK (phase IN ('Bull', 'Bear', 'Neutral')),
    
    -- 技术指标
    last_close NUMERIC NOT NULL,
    ma_short NUMERIC NOT NULL,
    ma_long NUMERIC NOT NULL,
    vp_corr NUMERIC NOT NULL,
    
    -- 市场信号
    funding_rate NUMERIC,
    stablecoin_flow NUMERIC,
    
    -- 判定原因（JSON格式存储）
    reasons JSONB NOT NULL,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    
    -- 唯一约束：同一交易所、交易对、时间点的判定结果唯一
    UNIQUE (exchange, symbol, datetime)
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_indecator_bull_bear_exchange_symbol ON public.indecator_bull_bear (exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_indecator_bull_bear_datetime ON public.indecator_bull_bear (datetime);
CREATE INDEX IF NOT EXISTS idx_indecator_bull_bear_phase ON public.indecator_bull_bear (phase);
CREATE INDEX IF NOT EXISTS idx_indecator_bull_bear_score ON public.indecator_bull_bear (score);

-- 添加表注释
COMMENT ON TABLE public.indecator_bull_bear IS '牛熊判定结果表，存储技术指标和市场信号的综合判定结果';

-- 添加字段注释
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
COMMENT ON COLUMN public.indecator_bull_bear.updated_at IS '记录更新时间';