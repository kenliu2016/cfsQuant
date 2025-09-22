---Binance 分钟 / 日 K 线

CREATE OR REPLACE FUNCTION fetch_binance_klines(p_interval text, table_name text)
RETURNS void AS $$
DECLARE
  url text;
  body text;
  j jsonb;
  elem jsonb;
  attempt int;
  ot bigint;
  o numeric; h numeric; l numeric; c numeric; v numeric;
  sym text;
  start_time TIMESTAMPTZ := clock_timestamp();
BEGIN
  -- 遍历 market_codes 表
  FOR sym IN 
    SELECT code 
    FROM market_codes 
    WHERE exchange = 'binance' AND active = true
  LOOP
    url := format(
      'https://api.binance.us/api/v3/klines?symbol=%s&interval=%s&limit=200', 
      sym, p_interval
    );

    body := NULL;
    FOR attempt IN 1..3 LOOP
      BEGIN
        body := (SELECT content FROM http_get(url, 'timeout=5000'));
        EXIT;
      EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Binance kline fetch failed for % (attempt %)', sym, attempt;
        PERFORM pg_sleep(2 * attempt);
      END;
    END LOOP;

    IF body IS NULL THEN
      CONTINUE;
    END IF;

    j := body::jsonb;
    FOR elem IN SELECT * FROM jsonb_array_elements(j) LOOP
      ot := (elem->>0)::bigint;
      o := (elem->>1)::numeric;
      h := (elem->>2)::numeric;
      l := (elem->>3)::numeric;
      c := (elem->>4)::numeric;
      v := (elem->>5)::numeric;

      IF p_interval = '1m' THEN
        EXECUTE format(
          'INSERT INTO %I (exchange,code,datetime,open,high,low,close,volume,raw)
           VALUES ($1,$2,to_timestamp($3/1000),$4,$5,$6,$7,$8,$9)
           ON CONFLICT (exchange,code,datetime) DO UPDATE
             SET open=$4,high=$5,low=$6,close=$7,volume=$8,raw=$9',
          table_name
        ) USING 'binance', sym, ot, o, h, l, c, v, elem;

      ELSIF p_interval = '1d' THEN
        EXECUTE format(
          'INSERT INTO %I (exchange,code,datetime,open,high,low,close,volume,raw)
           VALUES ($1,$2,to_timestamp($3/1000)::date,$4,$5,$6,$7,$8,$9)
           ON CONFLICT (exchange,code,datetime) DO UPDATE
             SET open=$4,high=$5,low=$6,close=$7,volume=$8,raw=$9',
          table_name
        ) USING 'binance', sym, ot, o, h, l, c, v, elem;
      END IF;
    END LOOP;
  END LOOP;

  -- 记录日志（如果你用了前面我写的 log_cron_job）
  PERFORM log_cron_job('fetch_binance_klines', 'success', 'Fetched Binance klines for active codes', start_time);

EXCEPTION WHEN OTHERS THEN
  PERFORM log_cron_job('fetch_binance_klines', 'error', SQLERRM, start_time);
  RAISE;
END;
$$ LANGUAGE plpgsql;




---OKX 分钟 / 日 K 线
CREATE OR REPLACE FUNCTION fetch_okx_klines(bar text, table_name text)
RETURNS void AS $$
DECLARE
  url text;
  body text;
  j jsonb;
  elem jsonb;
  attempt int;
  ot bigint;
  o numeric; h numeric; l numeric; c numeric; v numeric;
  sym text;
  start_time TIMESTAMPTZ := clock_timestamp();
BEGIN
  -- 遍历 market_codes 表
  FOR sym IN 
    SELECT code 
    FROM market_codes 
    WHERE exchange = 'okx' AND active = true
  LOOP
    url := format(
      'https://www.okx.com/api/v5/market/candles?instId=%s&bar=%s&limit=100',
      sym, bar
    );

    body := NULL;
    FOR attempt IN 1..3 LOOP
      BEGIN
        body := (SELECT content FROM http_get(url, 'timeout=5000'));
        EXIT;
      EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'OKX kline fetch failed for % (attempt %)', sym, attempt;
        PERFORM pg_sleep(2 * attempt);
      END;
    END LOOP;

    IF body IS NULL THEN
      CONTINUE;
    END IF;

    j := (body::jsonb)->'data';
    FOR elem IN SELECT * FROM jsonb_array_elements(j) LOOP
      ot := (elem->>0)::bigint;
      o := (elem->>1)::numeric;
      h := (elem->>2)::numeric;
      l := (elem->>3)::numeric;
      c := (elem->>4)::numeric;
      v := (elem->>5)::numeric;

      IF bar = '1m' THEN
        EXECUTE format(
          'INSERT INTO %I (exchange,code,datetime,open,high,low,close,volume,raw)
           VALUES ($1,$2,to_timestamp($3/1000),$4,$5,$6,$7,$8,$9)
           ON CONFLICT (exchange,code,datetime) DO UPDATE
             SET open=$4,high=$5,low=$6,close=$7,volume=$8,raw=$9',
          table_name
        ) USING 'okx', sym, ot, o, h, l, c, v, elem;

      ELSIF bar = '1D' THEN
        EXECUTE format(
          'INSERT INTO %I (exchange,code,datetime,open,high,low,close,volume,raw)
           VALUES ($1,$2,to_timestamp($3/1000)::date,$4,$5,$6,$7,$8,$9)
           ON CONFLICT (exchange,code,datetime) DO UPDATE
             SET open=$4,high=$5,low=$6,close=$7,volume=$8,raw=$9',
          table_name
        ) USING 'okx', sym, ot, o, h, l, c, v, elem;
      END IF;
    END LOOP;
  END LOOP;

  -- 成功写日志
  PERFORM log_cron_job('fetch_okx_klines', 'success', 'Fetched OKX klines for active codes', start_time);

EXCEPTION WHEN OTHERS THEN
  -- 出错写日志
  PERFORM log_cron_job('fetch_okx_klines', 'error', SQLERRM, start_time);
  RAISE;
END;
$$ LANGUAGE plpgsql;


--
SELECT cron.schedule('* * * * *',
$$
  SELECT fetch_binance_klines('1m', 'realtime_minute');
  SELECT fetch_okx_klines('1m', 'realtime_minute');
$$);


SELECT cron.schedule('5 0 * * *',
$$
  SELECT fetch_binance_klines('1d', 'realtime_daily');
  SELECT fetch_okx_klines('1D', 'realtime_daily');
$$);

