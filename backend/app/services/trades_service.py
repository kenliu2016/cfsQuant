import pandas as pd
from ..db import fetch_df

def get_trades_by_run_id(run_id: str) -> pd.DataFrame:
    """
    根据run_id获取交易记录
    
    Args:
        run_id: 回测运行ID
        
    Returns:
        包含交易记录的DataFrame
    """
    try:
        query = """SELECT run_id, datetime, code, side, price, qty, amount, fee
                    FROM trades
                    WHERE run_id = :run_id
                    ORDER BY datetime"""
        df = fetch_df(query, run_id=run_id)
        return df
    except Exception as e:
        print(f"获取交易记录失败: {e}")
        return pd.DataFrame()