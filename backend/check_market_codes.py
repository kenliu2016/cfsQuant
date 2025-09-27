import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import fetch_df

try:
    # 查询market_codes表的前10行数据
    df = fetch_df('SELECT * FROM market_codes LIMIT 10')
    print(f'market_codes表中前10行数据: {df.shape[0]}行')
    if not df.empty:
        print('数据预览:')
        print(df.head())
    else:
        print('market_codes表为空')
    
    # 检查active字段的值分布
    if not df.empty and 'active' in df.columns:
        active_counts = df['active'].value_counts()
        print('active字段分布:')
        print(active_counts)
except Exception as e:
    print(f'查询出错: {e}')