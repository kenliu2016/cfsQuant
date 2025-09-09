import pandas as pd
from app.db import fetch_df

# 检查是否能连接到数据库并查询equity表
try:
    # 检查runs表是否有数据
    runs_df = fetch_df("SELECT * FROM runs LIMIT 5")
    print("Runs表数据预览:")
    print(runs_df)
    print("\n")
    
    # 检查equity_curve表是否存在并查询数据（equity_curve表全面取代equity表）
    try:
        equity_df = fetch_df("SELECT * FROM equity_curve LIMIT 5")
        print("Equity_curve表数据预览:")
        print(equity_df)
        print(f"Equity_curve表共有 {len(equity_df)} 条记录")
    except Exception as e:
        print(f"查询equity_curve表时出错: {e}")
        
    # 检查是否有最近的回测运行
    recent_runs = fetch_df("SELECT run_id FROM runs ORDER BY start_time DESC LIMIT 1")
    if not recent_runs.empty:
        recent_run_id = recent_runs['run_id'].iloc[0]
        print(f"\n最近的回测ID: {recent_run_id}")
        
        # 检查该回测是否有equity_curve数据（equity_curve表全面取代equity表）
        try:
            recent_equity = fetch_df("SELECT * FROM equity_curve WHERE run_id = :rid", rid=recent_run_id)
            print(f"该回测的equity_curve记录数: {len(recent_equity)}")
        except Exception as e:
            print(f"查询该回测的equity_curve数据时出错: {e}")
            
    # 检查数据库表结构
    try:
        tables_df = fetch_df("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        print("\n数据库中的表:")
        print(tables_df)
    except Exception as e:
        print(f"查询表结构时出错: {e}")
        
except Exception as e:
    print(f"连接数据库时出错: {e}")