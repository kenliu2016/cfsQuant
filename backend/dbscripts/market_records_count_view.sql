-- 创建视图，统计三个表中每个exchange和code的记录数

-- 先删除视图（如果存在）
DROP VIEW IF EXISTS public.market_records_count;

-- 然后创建新视图
CREATE VIEW public.market_records_count AS
WITH minute_counts AS (
    SELECT 
        exchange, 
        code, 
        COUNT(*) AS minute_count
    FROM 
        public.minute_realtime
    GROUP BY 
        exchange, 
        code
),
hour_counts AS (
    SELECT 
        exchange, 
        code, 
        COUNT(*) AS hour_count
    FROM 
        public.hour_realtime
    GROUP BY 
        exchange, 
        code
),
day_counts AS (
    SELECT 
        exchange, 
        code, 
        COUNT(*) AS day_count
    FROM 
        public.day_realtime
    GROUP BY 
        exchange, 
        code
),
all_exchanges_codes AS (
    SELECT DISTINCT 
        exchange, 
        excode as code 
    FROM 
        public.market_codes
    UNION
    SELECT DISTINCT 
        exchange, 
        code 
    FROM 
        public.minute_realtime
    UNION
    SELECT DISTINCT 
        exchange, 
        code 
    FROM 
        public.hour_realtime
    UNION
    SELECT DISTINCT 
        exchange, 
        code 
    FROM 
        public.day_realtime
)
SELECT 
    a.exchange,
    a.code,
    COALESCE(m.minute_count, 0) AS minute_count,
    COALESCE(h.hour_count, 0) AS hour_count,
    COALESCE(d.day_count, 0) AS day_count,
    COALESCE(m.minute_count, 0) + COALESCE(h.hour_count, 0) + COALESCE(d.day_count, 0) AS total_count
FROM 
    all_exchanges_codes a
LEFT JOIN 
    minute_counts m ON a.exchange = m.exchange AND a.code = m.code
LEFT JOIN 
    hour_counts h ON a.exchange = h.exchange AND a.code = h.code
LEFT JOIN 
    day_counts d ON a.exchange = d.exchange AND a.code = d.code
ORDER BY 
    a.exchange, 
    a.code;