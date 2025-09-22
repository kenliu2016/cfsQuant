-- 订阅的交易对
CREATE TABLE IF NOT EXISTS market_symbols (
    exchange text NOT NULL,        -- 'binance' 或 'okx'
    symbol text NOT NULL,          -- binance/okx 的 API 使用的交易对形式
    active boolean NOT NULL DEFAULT true,
    PRIMARY KEY (exchange, symbol)
);

-- 初始化（示例：BTCUSDT, ETHUSDT, BNBUSDT）
INSERT INTO market_symbols(exchange, symbol) VALUES
  ('binance','BTCUSDT'),
  ('binance','ETHUSDT'),
  ('binance','BNBUSDT'),
  ('okx','BTC-USDT'),
  ('okx','ETH-USDT'),
  ('okx','BNB-USDT')
ON CONFLICT DO NOTHING;

INSERT INTO market_symbols(exchange, symbol) VALUES ('binance','XRPUSDT');


CREATE TABLE IF NOT EXISTS market_price (
    exchange text NOT NULL,
    symbol text NOT NULL,
    price numeric NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    raw jsonb,
    PRIMARY KEY (exchange, symbol)
);

CREATE TABLE IF NOT EXISTS market_price_history (
    id bigserial PRIMARY KEY,
    exchange text NOT NULL,
    symbol text NOT NULL,
    price numeric NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    raw jsonb
);


CREATE TABLE IF NOT EXISTS market_kline_minute (
    exchange text NOT NULL,
    symbol text NOT NULL,
    open_time timestamptz NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric,
    raw jsonb,
    PRIMARY KEY (exchange, symbol, open_time)
);


CREATE TABLE IF NOT EXISTS market_kline_daily (
    exchange text NOT NULL,
    symbol text NOT NULL,
    open_time date NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric,
    raw jsonb,
    PRIMARY KEY (exchange, symbol, open_time)
);

-- 分钟行情表
CREATE TABLE IF NOT EXISTS market_price_min (
    id bigserial PRIMARY KEY,
    exchange text NOT NULL,
    symbol text NOT NULL,
    price numeric NOT NULL,
    ts timestamptz NOT NULL,   -- 对齐到分钟
    raw jsonb
);

-- 日行情表
CREATE TABLE IF NOT EXISTS market_price_day (
    id bigserial PRIMARY KEY,
    exchange text NOT NULL,
    symbol text NOT NULL,
    open numeric NOT NULL,
    high numeric NOT NULL,
    low numeric NOT NULL,
    close numeric NOT NULL,
    volume numeric,
    ts date NOT NULL,          -- 对齐到日
    raw jsonb
);

