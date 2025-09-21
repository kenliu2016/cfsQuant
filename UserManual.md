# 📑 策略开发约定文档

## 1. 输入数据
引擎会传入一个 `pandas.DataFrame`，包含以下基础字段：
- `datetime` （时间，按升序排列）
- `open, high, low, close, volume` （行情数据）

策略可以在此基础上自行添加计算列。

---

## 2. 输出数据
策略的 `run(df, params)` 必须返回一个 `DataFrame`，至少包含以下字段：
- `datetime` （时间戳，对齐输入数据）
- `close` （收盘价，对齐输入数据）
- `position` （目标仓位比例，0.0~1.0 之间，代表满仓比例）

可选字段（仅用于调试/可视化，不参与回测核心逻辑）：
- `signal` （买卖信号，+1=买入，-1=卖出，0=无动作）
- `buy_signal`, `sell_signal` （二进制标记，方便画图）
- 其他中间计算指标（如 `trend_ma`, `grid_pos`）

---

## 3. 策略参数

### ✅ 允许包含（策略逻辑相关）
- **网格/指标逻辑**：如 `grid_num`, `lookback`, `trend_window`
- **趋势过滤**：如 `trend_filter`
- **风控条件**：如 `stop_loss_pct`, `take_profit_pct`
- **资金使用策略**：如 `used_capital_ratio`

### ❌ 禁止包含（引擎负责的执行参数）
以下由 **回测引擎统一管理**，策略里不能定义：
- `initial_capital` （初始资金）
- `fee_rate` （手续费）
- `slippage` （滑点）
- `cooldown_bars` （冷却周期）
- `min_trade_amount` （最小成交金额）
- `min_trade_qty` （最小成交数量）
- `lot_size` （最小交易单位）
- `min_position_change` （仓位变动阈值）

---

## 4. 开发原则
- **策略只决定目标仓位**，不负责成交逻辑。  
- **引擎决定能否成交**（资金是否足够、是否触发冷却期、交易费用等）。  
- **策略与引擎解耦**：策略可单独运行做信号可视化，引擎统一负责交易回测。  



# 拉取日线历史 + 订阅日线实时数据
python app/cli_ingest_1k_ws.py --interval 1m

# 只拉取分钟线历史数据
python app/cli_ingest_1k_ws.py --rest-only --interval 1m

# Binance 数据适配器用法示例
1. 批量并发拉取多个交易对
python -m app.cli_ingest_history --symbols BTCUSDT,ETHUSDT,BNBUSDT --interval 1m --start 2025-09-15 --end 2025-09-21--force --workers 3

这里 --workers 3 表示同时开 3 个线程，分别拉不同交易对。

2. 单币种（默认 1 个线程）
python -m app.cli_ingest_history --symbols BTCUSDT --interval 1d --start 2025-09-01 --end 2025-09-16 --force
