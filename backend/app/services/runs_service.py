
import pandas as pd
from ..db import fetch_df

def recent_runs(limit: int = 20) -> pd.DataFrame:
    sql = """
    SELECT run_id, strategy, code, start, end, initial_capital, final_capital
    FROM runs ORDER BY start DESC LIMIT :limit
    """
    return fetch_df(sql, limit=limit)

def run_detail(run_id: str):
    df_m = fetch_df("SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid", rid=run_id)
    df_e = fetch_df("SELECT datetime, nav, drawdown FROM equity WHERE run_id=:rid ORDER BY datetime", rid=run_id)
    return df_m, df_e
