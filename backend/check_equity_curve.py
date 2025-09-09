from app.db import fetch_df

# 检查equity_curve表是否存在以及是否有数据
try:
    df = fetch_df('SELECT * FROM equity_curve LIMIT 5')
    print('Equity_curve表数据预览:')
    print(df)
    if not df.empty:
        print(f'共有 {len(df)} 条记录')
    else:
        print('Equity_curve表为空')
except Exception as e:
    print(f'查询equity_curve表时出错: {e}')