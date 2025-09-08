from ..db import fetch_df
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
    # Filter minute_realtime where time is 23:59:00 to represent day-end bars
    sql = """
    SELECT datetime, code, open, high, low, close, volume
    FROM minute_realtime
    WHERE code = :code AND datetime BETWEEN :start AND :end
      AND EXTRACT(HOUR FROM datetime) = 23 AND EXTRACT(MINUTE FROM datetime) = 59
    ORDER BY datetime
    """
    return fetch_df(sql, code=code, start=start, end=end)


def get_intraday(code: str, start: str, end: str):
    # minute bars directly
    return get_candles(code, start, end, '1m')
