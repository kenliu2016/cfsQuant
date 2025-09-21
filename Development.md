# 解耦架构使用指南

## 🏗️ 新架构设计原则

### 核心理念
- **策略只决定目标仓位**，专注于信号生成逻辑
- **引擎决定能否成交**，统一处理交易执行
- **策略与引擎解耦**，各自独立，便于开发和测试

### 架构优势

| 优势 | 说明 | 效果 |
|------|------|------|
| **职责分离** | 策略专注信号，引擎专注执行 | 代码更清晰，易维护 |
| **独立开发** | 策略可单独开发测试 | 提升开发效率 |
| **统一框架** | 一个引擎支持所有策略 | 减少重复代码 |
| **可视化友好** | 策略可独立运行做信号分析 | 便于策略调试 |
| **风控统一** | 引擎统一处理风险控制 | 风控逻辑一致性 |

## 🚀 快速开始

### 1. 策略独立运行（信号可视化）

```python
from backend.core.strategies.grid_fixed_strategy import run as grid_strategy
from backend.app.services.backtest_service import run_strategy_only

# 方法1：直接调用策略
result = grid_strategy(df, {
    'N': 20,
    'H_price': 105,
    'L_price': 95,
    'R': 0.8
})

print(f"生成信号数量: {len(result['signals'])}")
print(f"网格级别: {len(result['auxiliary_data']['grid_levels'])}")

# 方法2：通过引擎加载（推荐）
result = run_strategy_only(df, {
    'N': 20,
    'R': 0.8  # H_price和L_price会自动推荐
}, 'grid_fixed_strategy')
```

### 2. 完整回测

```python
from backend.app.services.backtest_service import run_backtest

# 运行完整回测
result = run_backtest(df, {
    'code': 'BTC/USDT',
    'initial_capital': 100000,
    'N': 20,
    'R': 0.8,
    'fee_rate': 0.001,
    'slippage': 0.0002
}, 'grid_fixed_strategy')

print(f"回测ID: {result['run_id']}")
print(f"最终收益率: {result['metrics']['final_return']:.2%}")
print(f"执行交易数: {result['metrics']['trade_count']}")
```

## 📊 策略开发指南

### 策略接口规范

```python
def run(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    策略主函数
    
    Args:
        df: OHLC数据，必须包含 datetime, open, high, low, close
        params: 策略参数字典
        
    Returns:
        {
            'signals': List[Dict],      # 必须：信号列表
            'auxiliary_data': Dict,     # 可选：辅助数据
            'alerts': List[str],        # 可选：警告信息  
            'strategy_metrics': Dict    # 可选：策略指标
        }
    """
```

### 信号格式规范

```python
signal = {
    'datetime': '2024-01-01T00:00:00',  # ISO格式时间戳
    'target_position': 0.8,             # 目标仓位 (0-1)
    'signal_strength': 0.9,             # 信号强度 (0-1)  
    'signal_type': 'grid',              # 信号类型
    'metadata': {                       # 额外信息
        'price': 100.5,
        'grid_level': 5
    }
}
```

### 开发新策略模板

```python
"""
新策略模板
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List

DEFAULT_PARAMS = {
    "param1": 10,
    "param2": 0.5,
    # 添加你的默认参数
}

def run(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    # 1. 参数合并
    strategy_params = {**DEFAULT_PARAMS, **params}
    
    # 2. 数据验证
    if df.empty:
        return {'signals': [], 'auxiliary_data': {}, 'alerts': ['数据为空'], 'strategy_metrics': {}}
    
    # 3. 计算指标和信号
    signals = []
    for _, row in df.iterrows():
        # 你的策略逻辑
        target_position = calculate_position(row, strategy_params)
        
        if target_position is not None:  # 只在需要时生成信号
            signals.append({
                'datetime': row['datetime'],
                'target_position': target_position,
                'signal_strength': 1.0,
                'signal_type': 'your_strategy',
                'metadata': {}
            })
    
    # 4. 返回结果
    return {
        'signals': signals,
        'auxiliary_data': {},  # 可选：支撑位、阻力位等
        'alerts': [],          # 可选：参数警告等
        'strategy_metrics': {} # 可选：策略特有指标
    }

def calculate_position(row, params):
    # 实现你的策略逻辑
    pass
```

## 🔧 高级使用

### 1. 策略信号分析

```python
from backend.core.strategies.grid_fixed_strategy import analyze_strategy

# 获取详细分析
analysis = analyze_strategy(df, {
    'N': 20,
    'R': 0.8
})

# 分析结果
print("策略指标:", analysis['strategy_metrics'])
print("仓位变化次数:", analysis['strategy_metrics']['total_position_changes'])
print("平均仓位利用率:", analysis['strategy_metrics']['position_utilization'])

# 可视化数据
position_timeline = analysis['analysis_data']['position_timeline']
signal_strength_timeline = analysis['analysis_data']['signal_strength_timeline']
```

### 2. 快速预览

```python
from backend.core.strategies.grid_fixed_strategy import quick_backtest_preview

# 获取带信号的DataFrame，用于快速图表分析
df_with_signals = quick_backtest_preview(df, {
    'N': 15,
    'R': 0.7
})

print(df_with_signals[['datetime', 'close', 'target_position']].tail())
```

### 3. 自定义风控参数

```python
# 通过引擎参数控制风控
result = run_backtest(df, {
    'code': 'ETH/USDT',
    'initial_capital': 50000,
    
    # 策略参数
    'N': 25,
    'R': 0.9,
    
    # 引擎风控参数
    'stop_loss_pct': 0.15,      # 15%止损
    'take_profit_pct': 0.20,    # 20%止盈
    'max_position': 0.8,        # 最大仓位80%
    'min_position_change': 0.03, # 最小仓位变动3%
    'cooldown_bars': 120,       # 冷却期120根K线
    
    # 交易参数
    'fee_rate': 0.001,
    'slippage': 0.0003,
    'min_trade_amount': 1000
}, 'grid_fixed_strategy')
```

## 📈 信号可视化示例

### 基础可视化

```python
import matplotlib.pyplot as plt
import pandas as pd

# 获取策略结果
result = run_strategy_only(df, {'N': 20, 'R': 0.8}, 'grid_fixed_strategy')

# 准备数据
signals = result['signals']
grid_levels = result['auxiliary_data']['grid_levels']

# 绘制价格和信号
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# 价格图
ax1.plot(df['datetime'], df['close'], label='价格', alpha=0.7)

# 网格级别
for level in grid_levels:
    if level['type'] == 'grid':
        ax1.axhline(y=level['price'], color='gray', linestyle='--', alpha=0.5)

# 信号点
for signal in signals:
    dt = pd.to_datetime(signal['datetime'])
    price = df[df['datetime'] == dt]['close'].iloc[0] if len(df[df['datetime'] == dt]) > 0 else None
    if price is not None:
        color = 'green' if signal['target_position'] > 0.5 else 'red'
        ax1.scatter(dt, price, c=color, s=30, alpha=0.7)

ax1.set_ylabel('价格')
ax1.legend()
ax1.set_title('网格策略信号')

# 仓位图
signal_df = pd.DataFrame(signals)
signal_df['datetime'] = pd.to_datetime(signal_df['datetime'])
ax2.plot(signal_df['datetime'], signal_df['target_position'], label='目标仓位', drawstyle='steps-post')
ax2.set_ylabel('仓位比例')
ax2.set_xlabel('时间')
ax2.legend()

plt.tight_layout()
plt.show()
```

### 高级分析图表

```python
# 生成综合分析图表
def create_strategy_dashboard(df, strategy_params):
    # 获取分析结果
    analysis = analyze_strategy(df, strategy_params)
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # 1. 价格和网格
    ax = axes[0, 0]
    ax.plot(df['datetime'], df['close'], label='价格')
    for level in analysis['auxiliary_data']['grid_levels']:
        if level['type'] == 'grid':
            ax.axhline(y=level['price'], color='gray', linestyle='--', alpha=0.3)
    ax.set_title('价格与网格级别')
    ax.legend()
    
    # 2. 仓位变化
    ax = axes[0, 1]
    position_timeline = analysis['analysis_data']['position_timeline']
    if position_timeline:
        times, positions = zip(*position_timeline)
        ax.plot(pd.to_datetime(times), positions, drawstyle='steps-post')
    ax.set_title('目标仓位变化')
    ax.set_ylabel('仓位比例')
    
    # 3. 信号强度
    ax = axes[1, 0]
    strength_timeline = analysis['analysis_data']['signal_strength_timeline']
    if strength_timeline:
        times, strengths = zip(*strength_timeline)
        ax.plot(pd.to_datetime(times), strengths, 'o-', alpha=0.7)
    ax.set_title('信号强度分布')
    ax.set_ylabel('信号强度')
    
    # 4. 策略指标
    ax = axes[1, 1]
    metrics = analysis['strategy_metrics']
    metric_names = ['signal_count', 'position_utilization', 'max_position_reached']
    metric_values = [metrics.get(name, 0) for name in metric_names]
    ax.bar(metric_names, metric_values)
    ax.set_title('策略关键指标')
    ax.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.show()
    
    return analysis

# 使用示例
analysis = create_strategy_dashboard(df, {'N': 20, 'R': 0.8})
```

## 🔄 开发工作流

### 1. 策略开发流程

```bash
# 1. 开发阶段：策略独立测试
result = run_strategy_only(df, params, 'your_strategy')

# 2. 分析阶段：详细分析
analysis = analyze_strategy(df, params)  # 如果策略支持

# 3. 预览阶段：快速可视化
df_preview = quick_backtest_preview(df, params)  # 如果策略支持

# 4. 回测阶段：完整回测
backtest_result = run_backtest(df, params, 'your_strategy')

# 5. 优化阶段：参数调优
# 重复步骤1-4，调整参数
```

### 2. 调试技巧

```python
# 开启详细日志
params['logging_enabled'] = True

# 降低交易门槛便于调试
params.update({
    'min_trade_amount': 100,    # 降低最小交易金额
    'min_position_change': 0.01, # 降低最小仓位变动
    'cooldown_bars': 0          # 关闭冷却期
})

# 运行回测查看详细日志
result = run_backtest(df, params, 'your_strategy')
```

## 🚨 注意事项

### 策略开发注意点

1. **信号频率控制**：避免每个K线都生成信号，只在仓位需要变化时生成
2. **目标仓位范围**：确保在0-1之间，1表示满仓
3. **时间戳格式**：使用pandas兼容的时间格式
4. **异常处理**：策略应该优雅处理异常数据
5. **参数验证**：验证输入参数的合理性

### 引擎使用注意点

1. **参数传递**：策略参数和引擎参数要分清
2. **风控优先级**：引擎风控会覆盖策略信号
3. **资金检查**：引擎会自动检查资金充足性
4. **交易限制**：引擎会应用各种交易限制（最小金额、冷却期等）

## 📚 更多示例

### 自定义MA策略示例

```python
# custom_ma_strategy.py
DEFAULT_PARAMS = {
    "fast_period": 5,
    "slow_period": 20,
    "position_size": 0.8
}

def run(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    strategy_params = {**DEFAULT_PARAMS, **params}
    
    # 计算移动平均
    df['ma_fast'] = df['close'].rolling(strategy_params['fast_period']).mean()
    df['ma_slow'] = df['close'].rolling(strategy_params['slow_period']).mean()
    
    signals = []
    prev_position = 0.0
    
    for _, row in df.iterrows():
        if pd.isna(row['ma_fast']) or pd.isna(row['ma_slow']):
            continue
            
        # 金叉做多，死叉平仓
        if row['ma_fast'] > row['ma_slow']:
            target_position = strategy_params['position_size']
        else:
            target_position = 0.0
        
        # 只在仓位变化时生成信号
        if abs(target_position - prev_position) > 0.01:
            signals.append({
                'datetime': row['datetime'],
                'target_position': target_position,
                'signal_strength': abs(row['ma_fast'] - row['ma_slow']) / row['close'],
                'signal_type': 'ma_cross',
                'metadata': {
                    'ma_fast': row['ma_fast'],
                    'ma_slow': row['ma_slow']
                }
            })
            prev_position = target_position
    
    return {
        'signals': signals,
        'auxiliary_data': {
            'indicators': {
                'ma_fast_period': strategy_params['fast_period'],
                'ma_slow_period': strategy_params['slow_period']
            }
        },
        'alerts': [],
        'strategy_metrics': {
            'signal_count': len(signals),
            'cross_frequency': len(signals) / len(df) if len(df) > 0 else 0
        }
    }
```

这个解耦架构让策略开发更加专注和高效，同时保持了系统的灵活性和可扩展性！