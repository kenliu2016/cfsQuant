import matplotlib.pyplot as plt
import pandas as pd
from app.db import get_engine

engine = get_engine()

# 读取 trades 表
trades = pd.read_sql("SELECT * FROM trades ORDER BY datetime", con=engine)

print(f"trades表总行数: {len(trades)}")

# 只保留卖出交易
sell_trades = trades[trades['side'] == 'sell'].copy()
print(f"卖出交易数量: {len(sell_trades)}")

if len(sell_trades) > 0:
    # 检查avg_price字段
    zero_avg_price_count = (sell_trades['avg_price'] == 0).sum()
    print(f"avg_price为0的卖出交易数量: {zero_avg_price_count}")
    
    # 由于avg_price为0，我们直接使用realized_pnl作为分析指标
    # 绘制realized_pnl分布图
    plt.figure(figsize=(10,6))
    # 限制数据范围以避免极端值影响图表显示
    pnl_min, pnl_max = sell_trades['realized_pnl'].quantile([0.05, 0.95])
    filtered_pnl = sell_trades[(sell_trades['realized_pnl'] >= pnl_min) & (sell_trades['realized_pnl'] <= pnl_max)]['realized_pnl']
    
    plt.hist(filtered_pnl, bins=50, color='skyblue', edgecolor='black')
    plt.title('Sell Trades Realized PnL Distribution')
    plt.xlabel('Realized PnL')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.show()
    
    # 找出亏损的交易
    losing_trades = sell_trades[sell_trades['realized_pnl'] < 0]
    print(f"\n亏损交易数量: {len(losing_trades)}")
    
    # 输出亏损交易详情
    if not losing_trades.empty:
        print("=== 亏损交易详情 ===")
        print(losing_trades[['datetime', 'code', 'price', 'qty', 'realized_pnl', 'nav']])
    
    # 统计整体盈亏情况
    total_pnl = sell_trades['realized_pnl'].sum()
    avg_pnl = sell_trades['realized_pnl'].mean()
    
    print(f"\n整体盈亏统计:")
    print(f"总盈亏: {total_pnl:.2f}")
    print(f"平均每笔盈亏: {avg_pnl:.2f}")
else:
    print("没有卖出交易数据可供分析。")
