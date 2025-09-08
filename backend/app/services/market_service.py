from ..db import fetch_df
from datetime import datetime, timedelta
import pandas as pd

def get_candles(code: str, start: str, end: str, interval: str = "1m"):
    sql = """
    SELECT datetime, code, open, high, low, close, volume
    FROM minute_realtime
    WHERE code = :code AND datetime BETWEEN :start AND :end
    ORDER BY datetime
    """
    return fetch_df(sql, code=code, start=start, end=end)

def get_predictions(code: str, start: str, end: str):
    sql = """
    SELECT datetime, code, open, high, low, close, volume
    FROM minute_prediction
    WHERE code = :code AND datetime BETWEEN :start AND :end
    ORDER BY datetime
    """
    return fetch_df(sql, code=code, start=start, end=end)


def get_daily_candles(code: str, start: str, end: str):
    # For BTCUSDT and other cryptocurrencies, use a more flexible approach
    # Group minute data by date to create daily candles
    sql = """
    SELECT 
        day AS datetime,
        code,
        first_open AS open,
        MAX(high) AS high,
        MIN(low) AS low,
        last_close AS close,
        SUM(volume) AS volume
    FROM (
        SELECT 
            DATE_TRUNC('day', datetime) AS day,
            code,
            datetime,
            open,
            high,
            low,
            close,
            volume,
            FIRST_VALUE(open) OVER (PARTITION BY DATE_TRUNC('day', datetime) ORDER BY datetime) AS first_open,
            LAST_VALUE(close) OVER (PARTITION BY DATE_TRUNC('day', datetime) ORDER BY datetime RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_close
        FROM minute_realtime
        WHERE code = :code AND datetime BETWEEN :start AND :end
    ) AS subquery
    GROUP BY day, code, first_open, last_close
    ORDER BY day
    """
    return fetch_df(sql, code=code, start=start, end=end)


def get_intraday(code: str, start: str, end: str):
    # minute bars directly
    return get_candles(code, start, end, '1m')
