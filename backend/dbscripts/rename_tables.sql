-- 数据库表重命名脚本
-- 执行此脚本前请备份数据库
-- 此脚本包含所有表、序列、索引的重命名操作

-- 1. 重命名backtest相关表
ALTER TABLE IF EXISTS public.orders RENAME TO backtest_orders;
ALTER TABLE IF EXISTS public.positions RENAME TO backtest_positions;
ALTER TABLE IF EXISTS public.reports RENAME TO backtest_reports;
ALTER TABLE IF EXISTS public.runs RENAME TO backtest_runs;
ALTER TABLE IF EXISTS public.equity_curve RENAME TO backtest_equity_curve;
ALTER TABLE IF EXISTS public.grid_levels RENAME TO backtest_grid_levels;
ALTER TABLE IF EXISTS public.metrics RENAME TO backtest_metrics;
ALTER TABLE IF EXISTS public.trades RENAME TO backtest_trades;

-- 2. 重命名indecator相关表
ALTER TABLE IF EXISTS public.vmr_metrics RENAME TO indecator_vmr;
ALTER TABLE IF EXISTS public.fear_greed_index RENAME TO indecator_fear_greed;
ALTER TABLE IF EXISTS public.hmm_signal_realtime RENAME TO indecator_hmm;
ALTER TABLE IF EXISTS public.market_signals RENAME TO indecator_metrics;

-- 3. 重命名market相关表
ALTER TABLE IF EXISTS public.day_realtime RENAME TO market_day_klines;
ALTER TABLE IF EXISTS public.hour_realtime RENAME TO market_hour_klines;
ALTER TABLE IF EXISTS public.minute_realtime RENAME TO market_minute_klines;

-- 4. 重命名sys相关表
ALTER TABLE IF EXISTS public.strategies RENAME TO sys_strategies;
ALTER TABLE IF EXISTS public.cron_log RENAME TO sys_cron_log;

-- 5. 重命名序列
ALTER SEQUENCE IF EXISTS public.fear_greed_index_id_seq RENAME TO indecator_fear_greed_id_seq;
ALTER SEQUENCE IF EXISTS public.grid_levels_id_seq RENAME TO backtest_grid_levels_id_seq;
ALTER SEQUENCE IF EXISTS public.hmm_signal_realtime_id_seq RENAME TO indecator_hmm_id_seq;
ALTER SEQUENCE IF EXISTS public.market_signals_id_seq RENAME TO indecator_metrics_id_seq;
ALTER SEQUENCE IF EXISTS public.strategies_id_seq RENAME TO sys_strategies_id_seq;
ALTER SEQUENCE IF EXISTS public.vmr_metrics_id_seq RENAME TO indecator_vmr_id_seq;-- 序列重命名
ALTER SEQUENCE IF EXISTS public.cron_log_id_seq RENAME TO sys_cron_log_id_seq;
ALTER SEQUENCE IF EXISTS public.indecator_fear_greed_id_seq RENAME TO indecator_fear_greed_id_seq;
ALTER SEQUENCE IF EXISTS public.indecator_hmm_id_seq RENAME TO indecator_hmm_id_seq;
ALTER SEQUENCE IF EXISTS public.indecator_metrics_id_seq RENAME TO indecator_metrics_id_seq;
ALTER SEQUENCE IF EXISTS public.indecator_vmr_id_seq RENAME TO indecator_vmr_id_seq;
ALTER SEQUENCE IF EXISTS public.sys_strategies_id_seq RENAME TO sys_strategies_id_seq;

-- 6. 重命名索引
-- backtest相关索引
ALTER INDEX IF EXISTS public.idx_metrics_run RENAME TO idx_backtest_metrics_run;

-- indecator相关索引
ALTER INDEX IF EXISTS public.market_signals_idx RENAME TO indecator_metrics_idx;
ALTER INDEX IF EXISTS public.indecator_metrics_idx RENAME TO idx_indecator_metrics_exchange_symbol_datetime;

-- 7. 更新视图market_records_count中的表引用
CREATE OR REPLACE VIEW public.market_records_count AS
 WITH minute_counts AS (
         SELECT market_minute_klines.exchange,
            market_minute_klines.code,
            count(*) AS minute_count
           FROM market_minute_klines
          GROUP BY market_minute_klines.exchange, market_minute_klines.code
        ), hour_counts AS (
         SELECT market_hour_klines.exchange,
            market_hour_klines.code,
            count(*) AS hour_count
           FROM market_hour_klines
          GROUP BY market_hour_klines.exchange, market_hour_klines.code
        ), day_counts AS (
         SELECT market_day_klines.exchange,
            market_day_klines.code,
            count(*) AS day_count
           FROM market_day_klines
          GROUP BY market_day_klines.exchange, market_day_klines.code
        ), all_exchanges_codes AS (
         SELECT DISTINCT market_codes.exchange,
            market_codes.excode AS code
           FROM market_codes
        UNION
         SELECT DISTINCT market_minute_klines.exchange,
            market_minute_klines.code
           FROM market_minute_klines
        UNION
         SELECT DISTINCT market_hour_klines.exchange,
            market_hour_klines.code
           FROM market_hour_klines
        UNION
         SELECT DISTINCT market_day_klines.exchange,
            market_day_klines.code
           FROM market_day_klines
        )
 SELECT a.exchange,
    a.code,
    COALESCE(m.minute_count, 0::bigint) AS minute_count,
    COALESCE(h.hour_count, 0::bigint) AS hour_count,
    COALESCE(d.day_count, 0::bigint) AS day_count,
    COALESCE(m.minute_count, 0::bigint) + COALESCE(h.hour_count, 0::bigint) + COALESCE(d.day_count, 0::bigint) AS total_count
   FROM all_exchanges_codes a
     LEFT JOIN minute_counts m ON a.exchange = m.exchange::text AND a.code = m.code::text
     LEFT JOIN hour_counts h ON a.exchange = h.exchange::text AND a.code = h.code::text
     LEFT JOIN day_counts d ON a.exchange = d.exchange::text AND a.code = d.code::text
  ORDER BY a.exchange, a.code;;

-- 8. 更新分区表命名
-- 重命名day_realtime分区表
ALTER TABLE IF EXISTS public.day_realtime_2022 RENAME TO market_day_klines_2022;
ALTER TABLE IF EXISTS public.day_realtime_2023 RENAME TO market_day_klines_2023;
ALTER TABLE IF EXISTS public.day_realtime_2024 RENAME TO market_day_klines_2024;
ALTER TABLE IF EXISTS public.day_realtime_2025 RENAME TO market_day_klines_2025;

-- 重命名hour_realtime分区表
ALTER TABLE IF EXISTS public.hour_realtime_2022_09 RENAME TO market_hour_klines_2022_09;
ALTER TABLE IF EXISTS public.hour_realtime_2022_10 RENAME TO market_hour_klines_2022_10;
ALTER TABLE IF EXISTS public.hour_realtime_2022_11 RENAME TO market_hour_klines_2022_11;
ALTER TABLE IF EXISTS public.hour_realtime_2022_12 RENAME TO market_hour_klines_2022_12;
ALTER TABLE IF EXISTS public.hour_realtime_2023_01 RENAME TO market_hour_klines_2023_01;
ALTER TABLE IF EXISTS public.hour_realtime_2023_02 RENAME TO market_hour_klines_2023_02;
ALTER TABLE IF EXISTS public.hour_realtime_2023_03 RENAME TO market_hour_klines_2023_03;
ALTER TABLE IF EXISTS public.hour_realtime_2023_04 RENAME TO market_hour_klines_2023_04;
ALTER TABLE IF EXISTS public.hour_realtime_2023_05 RENAME TO market_hour_klines_2023_05;
ALTER TABLE IF EXISTS public.hour_realtime_2023_06 RENAME TO market_hour_klines_2023_06;
ALTER TABLE IF EXISTS public.hour_realtime_2023_07 RENAME TO market_hour_klines_2023_07;
ALTER TABLE IF EXISTS public.hour_realtime_2023_08 RENAME TO market_hour_klines_2023_08;
ALTER TABLE IF EXISTS public.hour_realtime_2023_09 RENAME TO market_hour_klines_2023_09;
ALTER TABLE IF EXISTS public.hour_realtime_2023_10 RENAME TO market_hour_klines_2023_10;
ALTER TABLE IF EXISTS public.hour_realtime_2023_11 RENAME TO market_hour_klines_2023_11;
ALTER TABLE IF EXISTS public.hour_realtime_2023_12 RENAME TO market_hour_klines_2023_12;
ALTER TABLE IF EXISTS public.hour_realtime_2024_01 RENAME TO market_hour_klines_2024_01;
ALTER TABLE IF EXISTS public.hour_realtime_2024_02 RENAME TO market_hour_klines_2024_02;
ALTER TABLE IF EXISTS public.hour_realtime_2024_03 RENAME TO market_hour_klines_2024_03;
ALTER TABLE IF EXISTS public.hour_realtime_2024_04 RENAME TO market_hour_klines_2024_04;
ALTER TABLE IF EXISTS public.hour_realtime_2024_05 RENAME TO market_hour_klines_2024_05;
ALTER TABLE IF EXISTS public.hour_realtime_2024_06 RENAME TO market_hour_klines_2024_06;
ALTER TABLE IF EXISTS public.hour_realtime_2024_07 RENAME TO market_hour_klines_2024_07;
ALTER TABLE IF EXISTS public.hour_realtime_2024_08 RENAME TO market_hour_klines_2024_08;
ALTER TABLE IF EXISTS public.hour_realtime_2024_09 RENAME TO market_hour_klines_2024_09;
ALTER TABLE IF EXISTS public.hour_realtime_2024_10 RENAME TO market_hour_klines_2024_10;
ALTER TABLE IF EXISTS public.hour_realtime_2024_11 RENAME TO market_hour_klines_2024_11;
ALTER TABLE IF EXISTS public.hour_realtime_2024_12 RENAME TO market_hour_klines_2024_12;
ALTER TABLE IF EXISTS public.hour_realtime_2025_01 RENAME TO market_hour_klines_2025_01;
ALTER TABLE IF EXISTS public.hour_realtime_2025_02 RENAME TO market_hour_klines_2025_02;
ALTER TABLE IF EXISTS public.hour_realtime_2025_03 RENAME TO market_hour_klines_2025_03;
ALTER TABLE IF EXISTS public.hour_realtime_2025_04 RENAME TO market_hour_klines_2025_04;
ALTER TABLE IF EXISTS public.hour_realtime_2025_05 RENAME TO market_hour_klines_2025_05;
ALTER TABLE IF EXISTS public.hour_realtime_2025_06 RENAME TO market_hour_klines_2025_06;
ALTER TABLE IF EXISTS public.hour_realtime_2025_07 RENAME TO market_hour_klines_2025_07;
ALTER TABLE IF EXISTS public.hour_realtime_2025_08 RENAME TO market_hour_klines_2025_08;
ALTER TABLE IF EXISTS public.hour_realtime_2025_09 RENAME TO market_hour_klines_2025_09;
ALTER TABLE IF EXISTS public.hour_realtime_2025_10 RENAME TO market_hour_klines_2025_10;
ALTER TABLE IF EXISTS public.hour_realtime_2025_11 RENAME TO market_hour_klines_2025_11;
ALTER TABLE IF EXISTS public.hour_realtime_2025_12 RENAME TO market_hour_klines_2025_12;

-- 重命名minute_realtime分区表
ALTER TABLE IF EXISTS public.minute_realtime_2022_09 RENAME TO market_minute_klines_2022_09;
ALTER TABLE IF EXISTS public.minute_realtime_2022_10 RENAME TO market_minute_klines_2022_10;
ALTER TABLE IF EXISTS public.minute_realtime_2022_11 RENAME TO market_minute_klines_2022_11;
ALTER TABLE IF EXISTS public.minute_realtime_2022_12 RENAME TO market_minute_klines_2022_12;
ALTER TABLE IF EXISTS public.minute_realtime_2023_01 RENAME TO market_minute_klines_2023_01;
ALTER TABLE IF EXISTS public.minute_realtime_2023_02 RENAME TO market_minute_klines_2023_02;
ALTER TABLE IF EXISTS public.minute_realtime_2023_03 RENAME TO market_minute_klines_2023_03;
ALTER TABLE IF EXISTS public.minute_realtime_2023_04 RENAME TO market_minute_klines_2023_04;
ALTER TABLE IF EXISTS public.minute_realtime_2023_05 RENAME TO market_minute_klines_2023_05;
ALTER TABLE IF EXISTS public.minute_realtime_2023_06 RENAME TO market_minute_klines_2023_06;
ALTER TABLE IF EXISTS public.minute_realtime_2023_07 RENAME TO market_minute_klines_2023_07;
ALTER TABLE IF EXISTS public.minute_realtime_2023_08 RENAME TO market_minute_klines_2023_08;
ALTER TABLE IF EXISTS public.minute_realtime_2023_09 RENAME TO market_minute_klines_2023_09;
ALTER TABLE IF EXISTS public.minute_realtime_2023_10 RENAME TO market_minute_klines_2023_10;
ALTER TABLE IF EXISTS public.minute_realtime_2023_11 RENAME TO market_minute_klines_2023_11;
ALTER TABLE IF EXISTS public.minute_realtime_2023_12 RENAME TO market_minute_klines_2023_12;
ALTER TABLE IF EXISTS public.minute_realtime_2024_01 RENAME TO market_minute_klines_2024_01;
ALTER TABLE IF EXISTS public.minute_realtime_2024_02 RENAME TO market_minute_klines_2024_02;
ALTER TABLE IF EXISTS public.minute_realtime_2024_03 RENAME TO market_minute_klines_2024_03;
ALTER TABLE IF EXISTS public.minute_realtime_2024_04 RENAME TO market_minute_klines_2024_04;
ALTER TABLE IF EXISTS public.minute_realtime_2024_05 RENAME TO market_minute_klines_2024_05;
ALTER TABLE IF EXISTS public.minute_realtime_2024_06 RENAME TO market_minute_klines_2024_06;
ALTER TABLE IF EXISTS public.minute_realtime_2024_07 RENAME TO market_minute_klines_2024_07;
ALTER TABLE IF EXISTS public.minute_realtime_2024_08 RENAME TO market_minute_klines_2024_08;
ALTER TABLE IF EXISTS public.minute_realtime_2024_09 RENAME TO market_minute_klines_2024_09;
ALTER TABLE IF EXISTS public.minute_realtime_2024_10 RENAME TO market_minute_klines_2024_10;
ALTER TABLE IF EXISTS public.minute_realtime_2024_11 RENAME TO market_minute_klines_2024_11;
ALTER TABLE IF EXISTS public.minute_realtime_2024_12 RENAME TO market_minute_klines_2024_12;
ALTER TABLE IF EXISTS public.minute_realtime_2025_01 RENAME TO market_minute_klines_2025_01;
ALTER TABLE IF EXISTS public.minute_realtime_2025_02 RENAME TO market_minute_klines_2025_02;
ALTER TABLE IF EXISTS public.minute_realtime_2025_03 RENAME TO market_minute_klines_2025_03;
ALTER TABLE IF EXISTS public.minute_realtime_2025_04 RENAME TO market_minute_klines_2025_04;
ALTER TABLE IF EXISTS public.minute_realtime_2025_05 RENAME TO market_minute_klines_2025_05;
ALTER TABLE IF EXISTS public.minute_realtime_2025_06 RENAME TO market_minute_klines_2025_06;
ALTER TABLE IF EXISTS public.minute_realtime_2025_07 RENAME TO market_minute_klines_2025_07;
ALTER TABLE IF EXISTS public.minute_realtime_2025_08 RENAME TO market_minute_klines_2025_08;
ALTER TABLE IF EXISTS public.minute_realtime_2025_09 RENAME TO market_minute_klines_2025_09;
ALTER TABLE IF EXISTS public.minute_realtime_2025_10 RENAME TO market_minute_klines_2025_10;
ALTER TABLE IF EXISTS public.minute_realtime_2025_11 RENAME TO market_minute_klines_2025_11;
ALTER TABLE IF EXISTS public.minute_realtime_2025_12 RENAME TO market_minute_klines_2025_12;

-- 9. 更新分区表索引命名
-- 重命名day_realtime分区表索引
ALTER INDEX IF EXISTS public.idx_day_realtime_2022_exchange_code_datetime RENAME TO idx_market_day_klines_2022_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_day_realtime_2023_exchange_code_datetime RENAME TO idx_market_day_klines_2023_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_day_realtime_2024_exchange_code_datetime RENAME TO idx_market_day_klines_2024_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_day_realtime_2025_exchange_code_datetime RENAME TO idx_market_day_klines_2025_exchange_code_datetime;

-- 重命名hour_realtime分区表索引
ALTER INDEX IF EXISTS public.idx_hour_realtime_2022_09_exchange_code_datetime RENAME TO idx_market_hour_klines_2022_09_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2022_10_exchange_code_datetime RENAME TO idx_market_hour_klines_2022_10_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2022_11_exchange_code_datetime RENAME TO idx_market_hour_klines_2022_11_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2022_12_exchange_code_datetime RENAME TO idx_market_hour_klines_2022_12_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_01_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_01_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_02_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_02_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_03_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_03_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_04_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_04_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_05_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_05_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_06_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_06_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_07_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_07_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_08_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_08_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_09_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_09_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_10_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_10_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_11_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_11_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2023_12_exchange_code_datetime RENAME TO idx_market_hour_klines_2023_12_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_01_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_01_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_02_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_02_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_03_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_03_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_04_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_04_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_05_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_05_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_06_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_06_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_07_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_07_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_08_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_08_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_09_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_09_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_10_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_10_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_11_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_11_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2024_12_exchange_code_datetime RENAME TO idx_market_hour_klines_2024_12_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_01_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_01_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_02_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_02_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_03_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_03_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_04_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_04_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_05_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_05_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_06_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_06_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_07_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_07_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_08_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_08_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_09_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_09_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_10_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_10_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_11_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_11_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_hour_realtime_2025_12_exchange_code_datetime RENAME TO idx_market_hour_klines_2025_12_exchange_code_datetime;

-- 重命名minute_realtime分区表索引
ALTER INDEX IF EXISTS public.idx_minute_realtime_2022_09_exchange_code_datetime RENAME TO idx_market_minute_klines_2022_09_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2022_10_exchange_code_datetime RENAME TO idx_market_minute_klines_2022_10_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2022_11_exchange_code_datetime RENAME TO idx_market_minute_klines_2022_11_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2022_12_exchange_code_datetime RENAME TO idx_market_minute_klines_2022_12_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_01_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_01_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_02_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_02_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_03_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_03_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_04_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_04_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_05_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_05_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_06_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_06_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_07_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_07_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_08_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_08_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_09_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_09_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_10_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_10_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_11_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_11_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2023_12_exchange_code_datetime RENAME TO idx_market_minute_klines_2023_12_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_01_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_01_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_02_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_02_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_03_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_03_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_04_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_04_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_05_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_05_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_06_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_06_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_07_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_07_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_08_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_08_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_09_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_09_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_10_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_10_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_11_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_11_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2024_12_exchange_code_datetime RENAME TO idx_market_minute_klines_2024_12_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_01_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_01_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_02_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_02_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_03_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_03_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_04_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_04_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_05_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_05_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_06_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_06_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_07_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_07_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_08_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_08_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_09_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_09_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_10_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_10_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_11_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_11_exchange_code_datetime;
ALTER INDEX IF EXISTS public.idx_minute_realtime_2025_12_exchange_code_datetime RENAME TO idx_market_minute_klines_2025_12_exchange_code_datetime;

-- 注意：由于分区表数量众多，建议在实际执行前先备份数据库，并根据实际的分区表结构进行重命名

-- 脚本执行完成提示
SELECT '数据库表重命名完成，请检查相关代码中的表引用是否已更新' AS message;