# Dashboard页面各元素计算逻辑文档

## 1. 强势弱势币选币逻辑

### 1.1 VMR（Volume-to-Market-Ratio）指标

#### 1.1.1 定义
VMR指标衡量交易量与市值的比率，反映单位市值对应的交易活跃度。

#### 1.1.2 业务意义
- **高VMR值**: 表示相对于市值，交易活跃度较高，可能存在投机性交易或市场关注度提升
- **低VMR值**: 表示交易相对冷清，市场关注度较低
- **应用场景**: 识别交易活跃度异常的币种，辅助判断市场情绪

#### 1.1.3 计算逻辑
```sql
vmr = volume / market_cap
```

**参数说明：**
- **volume**: 24小时交易量（单位：基础货币数量）
- **market_cap**: 当前市值（单位：美元）
- **数据来源**: `market_ohlcv_1h` 表中的累计数据

**计算示例：**
- 某币种24小时交易量：1,000,000枚
- 当前市值：100,000,000美元
- VMR = 1,000,000 / 100,000,000 = 0.01

#### 1.1.4 数值解读
- **正常范围**: 0.001-0.1（不同币种差异较大）
- **异常高值**: >0.1，可能表示过度投机
- **异常低值**: <0.001，可能表示流动性不足

### 1.2 涨跌幅指标

#### 1.2.1 定义
涨跌幅指标衡量币种在特定时间段内的价格变化百分比。

#### 1.2.2 业务意义
- **正涨跌幅**: 价格上涨，反映市场看涨情绪
- **负涨跌幅**: 价格下跌，反映市场看跌情绪
- **应用场景**: 识别短期价格动量，判断市场趋势方向

#### 1.2.3 计算逻辑
```sql
price_change = (current_price - previous_price) / previous_price × 100%
```

**参数说明：**
- **current_price**: 当前价格（最新K线收盘价）
- **previous_price**: 参考价格（24小时前价格）
- **时间窗口**: 24小时（可根据需求调整）

#### 1.2.4 数值解读
- **强势标准**: >5%（显著上涨）
- **弱势标准**: <-5%（显著下跌）
- **震荡区间**: -5%到5%（无明显趋势）

### 1.3 复合分数计算逻辑

#### 1.3.1 权重分配原理
强势弱势币的综合评分采用加权平均公式：
```sql
综合分数 = 涨跌幅 × 40% + VE指标 × 30% + VMR × 30%
```

**权重分配依据：**
- **涨跌幅（40%）**: 最高权重，反映短期价格动量是选币的核心因素
- **VE指标（30%）**: 中等权重，衡量交易效率的质量
- **VMR（30%）**: 中等权重，反映交易活跃度

#### 1.3.2 标准化处理
各指标在计算前需要进行标准化处理：
```python
# 标准化公式
normalized_value = (raw_value - min_value) / (max_value - min_value)
```

**标准化目的：**
- 消除不同指标的量纲差异
- 确保各指标在相同尺度上比较
- 避免单一指标主导综合评分

### 1.3 排序规则
1. **强势币排序**: 按综合分数降序排列，分数越高越强势
2. **弱势币排序**: 按综合分数升序排列，分数越低越弱势

### 1.4 选币规则
- 从所有可交易币种中筛选
- 排除流动性不足的币种（交易量低于阈值）
- 选择排名前N的币种作为强势/弱势币

## 2. 币种分析表查询逻辑

### 2.1 VE（Volatility Efficiency）波动率效率指标

#### 2.1.1 定义
VE指标衡量单位波动率产生的交易效率，是成交量效率和波动率效率的乘积。

#### 2.1.2 业务意义
- **高VE值**: 表示在相同波动率下交易效率更高，市场运行更健康
- **低VE值**: 表示交易效率低下，可能存在流动性问题或市场异常
- **应用场景**: 评估币种交易质量，识别高效交易机会

#### 2.1.3 核心计算公式
```
VE = 成交量效率 × 波动率效率
```

### 2.2 成交量效率子指标

#### 2.2.1 定义
成交量效率衡量当前成交量相对于历史平均成交量的比率。

#### 2.2.2 业务意义
- **>1**: 当前成交量高于历史平均水平，市场活跃
- **<1**: 当前成交量低于历史平均水平，市场相对冷清
- **异常值**: 极端高值可能表示异常交易活动

#### 2.2.3 计算逻辑
```python
volume_efficiency = current_volume / historical_avg_volume
```

**参数说明：**
- **current_volume**: 当前周期成交量
- **historical_avg_volume**: 历史平均成交量（20周期移动平均）
- **平滑处理**: 对极端值进行限制（0.1 ≤ volume_efficiency ≤ 10.0）

#### 2.2.4 实现细节
```python
def calculate_volume_efficiency(df, window=20):
    current_volume = df['volume'].iloc[-1]
    avg_volume = df['volume'].rolling(window=window).mean().iloc[-1]
    
    if avg_volume == 0:
        return 1.0  # 避免除零错误
        
    volume_efficiency = current_volume / avg_volume
    # 平滑处理极端值
    volume_efficiency = min(max(volume_efficiency, 0.1), 10.0)
    return volume_efficiency
```

### 2.3 波动率效率子指标

#### 2.3.1 定义
波动率效率衡量实际波动率相对于预期波动率的比率。

#### 2.3.2 业务意义
- **>1**: 实际波动率高于预期，市场波动性增强
- **<1**: 实际波动率低于预期，市场相对稳定
- **平衡点**: 接近1表示波动率符合预期

#### 2.3.3 计算逻辑
```python
volatility_efficiency = actual_volatility / expected_volatility
```

### 2.4 实际波动率计算

#### 2.4.1 定义
基于对数收益率的年化波动率，反映价格的实际波动程度。

#### 2.4.2 计算逻辑
```python
def calculate_actual_volatility(df, window=20):
    # 计算对数收益率
    returns = np.log(df['close'] / df['close'].shift(1))
    returns = returns.dropna()
    
    # 计算滚动标准差并取平均
    rolling_std = returns.rolling(window=window).std()
    actual_volatility = rolling_std.mean() * np.sqrt(252)  # 年化
    
    return actual_volatility
```

**参数说明：**
- **对数收益率**: 更符合金融数据的统计特性
- **年化处理**: 乘以√252（年交易日数）
- **窗口大小**: 20周期，可根据市场特性调整

### 2.5 预期波动率计算

#### 2.5.1 定义
基于历史波动率的移动平均，作为未来波动率的预期基准。

#### 2.5.2 计算逻辑
```python
def calculate_expected_volatility(df, window=20):
    # 计算百分比收益率
    returns = df['close'].pct_change()
    returns = returns.dropna()
    
    # 计算历史波动率的移动平均
    historical_volatility = returns.rolling(window=window).std()
    expected_volatility = historical_volatility.mean() * np.sqrt(252)
    
    return expected_volatility
```

**实现特点：**
- **稳健性**: 使用移动平均平滑历史波动率
- **适应性**: 窗口大小可根据市场周期调整
- **连续性**: 确保预期波动率的连续性

### 2.2 复合分数计算逻辑
币种分析表的综合评分采用均衡权重：
```sql
综合分数 = 市值 × 25% + 成交量 × 25% + VE指标 × 25% + VMR × 25%
```

**各指标权重说明：**
- **市值（25%）**: 反映币种规模和市场地位
- **成交量（25%）**: 反映交易活跃度
- **VE指标（25%）**: 波动率效率指标
- **VMR（25%）**: 交易活跃度指标

## 3. 牛熊市指标计算逻辑

### 3.1 移动平均线指标

#### 3.1.1 定义
移动平均线是通过计算特定周期内价格的平均值来平滑价格波动的技术指标。

#### 3.1.2 业务意义
- **短期MA（50周期）**: 反映近期价格趋势，对价格变化敏感
- **长期MA（200周期）**: 反映长期价格趋势，稳定性较高
- **金叉/死叉**: 短期MA上穿/下穿长期MA是重要的趋势转换信号

#### 3.1.3 计算逻辑
```python
def compute_mas(df, short=50, long=200):
    df['ma_short'] = df['close'].rolling(window=short, min_periods=1).mean()
    df['ma_long'] = df['close'].rolling(window=long, min_periods=1).mean()
    return df
```

**参数说明：**
- **窗口大小**: 短期50周期，长期200周期（经典技术分析参数）
- **min_periods=1**: 确保即使数据不足也能计算
- **数据源**: 使用收盘价计算

#### 3.1.4 信号判断
- **看涨信号**: 价格 > 长期MA 且 短期MA > 长期MA
- **看跌信号**: 价格 < 长期MA 且 短期MA < 长期MA
- **震荡信号**: MA关系不明确

### 3.2 价格结构斜率

#### 3.2.1 定义
通过线性回归分析价格高点和低点的趋势斜率，判断价格结构的变化。

#### 3.2.2 业务意义
- **高点斜率**: 反映阻力位的变化趋势
- **低点斜率**: 反映支撑位的变化趋势
- **趋势确认**: 高点更高、低点更高确认上升趋势

#### 3.2.3 计算逻辑
```python
def price_structure_slopes(df):
    # 重采样为小时级数据
    highs = df['high'].resample('1h').max().dropna()
    lows = df['low'].resample('1h').min().dropna()
    
    def slope(series):
        if len(series) < 3: return 0.0
        x = np.arange(len(series))
        return float(np.polyfit(x, series.values, 1)[0])
    
    return slope(highs[-24:]), slope(lows[-24:])
```

**实现细节：**
- **重采样**: 将分钟级数据转为小时级，减少噪音
- **时间窗口**: 分析最近24小时的价格结构
- **线性回归**: 使用一次多项式拟合趋势线

#### 3.2.4 趋势判断
- **上升趋势**: 高点斜率 > 0 且 低点斜率 > 0
- **下降趋势**: 高点斜率 < 0 且 低点斜率 < 0
- **震荡趋势**: 斜率符号不一致

### 3.3 量价相关性

#### 3.3.1 定义
衡量价格变化率与成交量变化率之间的统计相关性。

#### 3.3.2 业务意义
- **正相关**: 价格上涨伴随成交量放大，趋势健康
- **负相关**: 价格上涨但成交量萎缩，趋势可能反转
- **无相关**: 价格与成交量关系不明确

#### 3.3.3 计算逻辑
```python
def vp_corr(df, window=24):
    w = min(len(df), window)
    price_change = df['close'].pct_change().fillna(0).tail(w)
    volume_change = df['volume'].pct_change().fillna(0).tail(w)
    
    if price_change.std() == 0 or volume_change.std() == 0:
        return 0.0
    
    return float(price_change.corr(volume_change))
```

**统计特性：**
- **皮尔逊相关系数**: 衡量线性相关程度
- **范围**: -1到1，0表示无相关性
- **显著性**: |r| > 0.1 认为有统计意义

### 3.4 资金费率信号

#### 3.4.1 定义
永续合约的资金费率，反映多空双方的资金成本。

#### 3.4.2 业务意义
- **正资金费率**: 多头支付空头，市场看涨情绪强烈
- **负资金费率**: 空头支付多头，市场看跌情绪强烈
- **极端值**: 高绝对值可能表示市场过度投机

#### 3.4.3 数据获取
```python
def fetch_latest_funding_rate(symbol='BTCUSDT'):
    url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1"
    response = requests.get(url, timeout=20)
    data = response.json()
    
    if isinstance(data, list) and data:
        return float(data[0].get('fundingRate', 0.0))
    return None
```

**数据特性：**
- **更新频率**: 每8小时更新一次
- **正常范围**: -0.1%到0.1%
- **异常范围**: 绝对值>0.5%可能表示市场异常

### 3.5 稳定币流入代理

#### 3.5.1 定义
通过稳定币相关交易对的交易量变化，间接反映市场资金流入情况。

#### 3.5.2 业务意义
- **流入增加**: 资金进入加密货币市场，看涨信号
- **流入减少**: 资金流出市场，看跌信号
- **趋势确认**: 结合其他指标确认市场方向

#### 3.5.3 计算逻辑
```python
def fetch_stablecoin_flow_proxy():
    url = 'https://api.binance.com/api/v3/ticker/24hr'
    response = requests.get(url, timeout=20)
    tickers = response.json()
    
    stablecoins = ['USDT', 'USDC', 'FDUSD', 'BUSD']
    total_quote_vol = 0.0
    count = 0
    
    for ticker in tickers:
        symbol = ticker.get('symbol', '')
        if any(st in symbol for st in stablecoins) and symbol.endswith('USDT'):
            quote_volume = float(ticker.get('quoteVolume', 0) or 0)
            if quote_volume > 0:
                total_quote_vol += quote_volume
                count += 1
    
    if count == 0:
        return None
    
    avg_volume = total_quote_vol / count
    # 缩放处理，便于存储和比较
    return float((avg_volume ** 0.5) / 1e3)
```

**实现特点：**
- **代理指标**: 无法直接获取稳定币流入数据，使用交易量作为代理
- **平均处理**: 计算所有稳定币交易对的平均交易量
- **缩放处理**: 对超大数值进行缩放，便于比较

### 3.6 综合评分逻辑

#### 3.6.1 权重分配原理
权重分配基于各指标对市场趋势预测的可靠性和时效性：

| 指标 | 权重 | 分配依据 |
|------|------|----------|
| 移动平均线 | 30% | 技术分析核心指标，趋势判断最可靠 |
| 价格结构斜率 | 25% | 反映价格结构变化，中期趋势重要指标 |
| 量价相关性 | 20% | 衡量趋势健康度，短期有效性高 |
| 资金费率 | 15% | 反映市场情绪，但易受短期投机影响 |
| 稳定币流入 | 10% | 代理指标，数据质量相对较低 |

#### 3.6.2 评分规则详细说明

**移动平均线评分：**
```python
def ma_score(df):
    latest = df.iloc[-1]
    if latest['close'] > latest['ma_long'] and latest['ma_short'] > latest['ma_long']:
        return 1.0  # 看涨
    elif latest['close'] < latest['ma_long'] and latest['ma_short'] < latest['ma_long']:
        return -1.0  # 看跌
    else:
        return 0.0  # 震荡
```

**价格结构斜率评分：**
```python
def slope_score(high_slope, low_slope):
    if high_slope > 0 and low_slope > 0:
        return 1.0  # 上升趋势
    elif high_slope < 0 and low_slope < 0:
        return -1.0  # 下降趋势
    else:
        return 0.0  # 震荡
```

**量价相关性评分：**
```python
def vp_corr_score(corr):
    if corr > 0.1:
        return 1.0  # 量价正相关，看涨
    elif corr < -0.1:
        return -1.0  # 量价负相关，看跌
    else:
        return 0.0  # 无明确信号
```

**资金费率评分：**
```python
def funding_rate_score(rate):
    if rate > 0.0005:  # 0.05%
        return 1.0  # 多头强势
    elif rate < -0.0005:  # -0.05%
        return -1.0  # 空头强势
    else:
        return 0.0  # 中性
```

**稳定币流入评分：**
```python
def stablecoin_score(current_flow, historical_avg):
    if current_flow > historical_avg * 1.1:
        return 1.0  # 资金流入增加
    elif current_flow < historical_avg * 0.9:
        return -1.0  # 资金流出
    else:
        return 0.0  # 稳定
```

#### 3.6.3 综合评分计算
```python
def composite_bull_bear_score(indicators):
    weights = {
        'ma': 0.30,
        'slope': 0.25,
        'vp_corr': 0.20,
        'funding_rate': 0.15,
        'stablecoin': 0.10
    }
    
    weighted_sum = 0.0
    for indicator, score in indicators.items():
        weighted_sum += score * weights[indicator]
    
    return weighted_sum
```

#### 3.6.4 牛熊判定阈值

**判定逻辑：**
- **牛市**: 综合评分 > 0.3
  - 市场处于明确上升趋势
  - 多数技术指标显示看涨信号
  - 建议采取积极投资策略

- **熊市**: 综合评分 < -0.3
  - 市场处于明确下降趋势
  - 多数技术指标显示看跌信号
  - 建议采取防御性投资策略

- **震荡市**: -0.3 ≤ 综合评分 ≤ 0.3
  - 市场方向不明确
  - 指标信号相互矛盾
  - 建议采取中性或观望策略

**阈值设定依据：**
- **0.3阈值**: 确保至少60%的指标权重支持同一方向
- **缓冲区间**: 避免频繁切换判定结果
- **历史回测**: 基于历史数据优化确定的最佳阈值

## 4. HMM模型计算原理和相关逻辑

### 4.1 隐藏状态定义

#### 4.1.1 状态分类与定义
HMM模型将市场状态分为5个隐藏状态，每个状态具有独特的统计特征：

| 状态 | 名称 | 波动率特征 | 趋势特征 | 市场情绪 |
|------|------|------------|----------|----------|
| 状态1 | 低波动率上涨 | 波动率低 | 稳定上涨 | 乐观 |
| 状态2 | 高波动率上涨 | 波动率高 | 剧烈上涨 | 狂热 |
| 状态3 | 低波动率下跌 | 波动率低 | 稳定下跌 | 悲观 |
| 状态4 | 高波动率下跌 | 波动率高 | 剧烈下跌 | 恐慌 |
| 状态5 | 震荡整理 | 波动率中等 | 横盘震荡 | 中性 |

#### 4.1.2 状态特征量化
每个隐藏状态由以下统计参数定义：
- **均值向量**: 反映各观测变量的平均水平
- **协方差矩阵**: 反映变量间的相关性和波动性
- **转移概率**: 状态间转换的可能性

### 4.2 观测序列构建

#### 4.2.1 观测变量选择
HMM模型使用以下观测变量构建观测序列：

```python
observation_variables = [
    'log_return',           # 对数收益率
    'volatility_5min',      # 5分钟波动率
    'volume_change',        # 成交量变化率
    'rsi_14',              # 14周期RSI
    'macd_diff'            # MACD差值
]
```

#### 4.2.2 特征工程方法

**对数收益率计算：**
```python
def log_returns(prices):
    return np.log(prices / prices.shift(1)).fillna(0)
```

**波动率计算（滚动标准差）：**
```python
def rolling_volatility(returns, window=12):
    return returns.rolling(window=window).std().fillna(0)
```

**数据标准化：**
```python
def standardize_features(df):
    scaler = StandardScaler()
    return scaler.fit_transform(df)
```

### 4.3 模型训练流程

#### 4.3.1 数据准备阶段
- **时间范围**: 使用最近2年的历史数据
- **数据频率**: 5分钟K线数据
- **数据清洗**: 处理缺失值和异常值

#### 4.3.2 模型参数优化

**状态数确定（BIC准则）：**
```python
def optimize_n_states(observations, max_states=10):
    bic_scores = []
    for n in range(2, max_states + 1):
        model = GaussianHMM(n_components=n, covariance_type="diag", n_iter=1000)
        model.fit(observations)
        bic_scores.append(model.bic(observations))
    
    return np.argmin(bic_scores) + 2  # 返回最优状态数
```

**EM算法训练：**
```python
def train_hmm_model(observations, n_states=5):
    model = GaussianHMM(
        n_components=n_states,
        covariance_type="diag",
        n_iter=1000,
        random_state=42
    )
    model.fit(observations)
    return model
```

#### 4.3.3 模型评估指标
- **对数似然**: 模型对数据的拟合程度
- **BIC值**: 平衡模型复杂度和拟合优度
- **状态稳定性**: 状态转移矩阵的稳定性

### 4.4 信号生成逻辑

#### 4.4.1 当前状态识别

**状态概率计算：**
```python
def get_current_state_probabilities(model, recent_observations):
    # 使用最近20个观测点（约2小时数据）
    logprob, state_sequence = model.decode(recent_observations)
    state_probs = model.predict_proba(recent_observations[-1:])[0]
    return state_probs, state_sequence
```

#### 4.4.2 交易信号生成规则

**信号强度计算：**
```python
def generate_trading_signals(state_probs):
    # 状态权重分配
    bullish_weight = state_probs[0] + state_probs[1] * 0.5  # 状态1全权重，状态2半权重
    bearish_weight = state_probs[2] + state_probs[3] * 0.5  # 状态3全权重，状态4半权重
    
    signal_strength = bullish_weight - bearish_weight
    
    if signal_strength > 0.6:
        return "STRONG_BUY", signal_strength
    elif signal_strength > 0.3:
        return "BUY", signal_strength
    elif signal_strength < -0.6:
        return "STRONG_SELL", signal_strength
    elif signal_strength < -0.3:
        return "SELL", signal_strength
    else:
        return "HOLD", signal_strength
```

#### 4.4.3 风险控制机制
- **信号确认**: 需要连续多个周期确认
- **止损设置**: 基于波动率动态调整
- **仓位管理**: 信号强度决定仓位大小

### 4.5 多时间周期分析

#### 4.5.1 周期配置策略

| 周期 | 数据频率 | 状态数 | 主要用途 |
|------|----------|--------|----------|
| 短期 | 5分钟 | 5 | 日内交易信号 |
| 中期 | 1小时 | 5 | 趋势方向判断 |
| 长期 | 日线 | 4 | 宏观趋势分析 |

#### 4.5.2 多周期信号融合

**信号权重分配：**
```python
def multi_timeframe_signal(short_signal, medium_signal, long_signal):
    weights = {'short': 0.4, 'medium': 0.35, 'long': 0.25}
    
    signal_map = {
        "STRONG_BUY": 2, "BUY": 1, "HOLD": 0,
        "SELL": -1, "STRONG_SELL": -2
    }
    
    weighted_score = (
        signal_map[short_signal] * weights['short'] +
        signal_map[medium_signal] * weights['medium'] +
        signal_map[long_signal] * weights['long']
    )
    
    return weighted_score
```

#### 4.5.3 周期协调机制
- **一致性检查**: 多周期信号方向一致时增强信心
- **冲突处理**: 短期与长期信号冲突时以长期为主
- **动态调整**: 根据市场波动性调整周期权重

### 4.6 质量监控机制

#### 4.6.1 模型质量检查
- **状态概率分布合理性**: 避免极端概率值
- **模型收敛性验证**: 确保训练过程收敛
- **状态切换频率检测**: 防止过度频繁的状态切换

#### 4.6.2 异常检测
- **极端概率值检测**: state_prob接近0或1
- **信号质量异常**: 信号生成逻辑异常
- **置信度过低**: 模型预测置信度不足

## 5. 数据更新机制

### 5.1 物化视图架构设计

#### 5.1.1 物化视图定义
物化视图是预先计算并存储的查询结果，提供高性能的数据访问：

```sql
-- 市场情绪物化视图定义
CREATE MATERIALIZED VIEW dashboard_market_sentiment AS
SELECT 
    time_bucket('15 minutes', datetime) AS bucket,
    symbol,
    AVG(bull_bear_score) AS market_sentiment,
    COUNT(*) AS data_count
FROM market_sentiment_data
WHERE datetime >= NOW() - INTERVAL '7 days'
GROUP BY bucket, symbol
ORDER BY bucket DESC, symbol;
```

#### 5.1.2 架构优势
- **查询性能**: 避免实时计算复杂聚合
- **数据一致性**: 确保所有用户看到相同数据
- **资源优化**: 减少数据库负载

### 5.2 连续聚合策略

#### 5.2.1 刷新频率配置
```sql
-- 配置15分钟刷新策略
SELECT add_continuous_aggregate_policy(
    'dashboard_market_sentiment',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '15 minutes'
);
```

**参数说明：**
- **start_offset**: 保留1小时数据用于边界处理
- **end_offset**: 延迟1分钟确保数据完整性
- **schedule_interval**: 15分钟刷新周期

#### 5.2.2 增量更新机制
- **时间窗口**: 只刷新最近时间窗口的数据
- **增量计算**: 避免全量刷新，提高效率
- **边界处理**: 正确处理时间窗口边界

### 5.3 索引优化策略

#### 5.3.1 复合索引设计
```sql
-- 为物化视图创建优化索引
CREATE INDEX CONCURRENTLY idx_dashboard_sentiment_time_symbol 
ON dashboard_market_sentiment (bucket DESC, symbol);

CREATE INDEX CONCURRENTLY idx_dashboard_coins_time_score 
ON dashboard_strong_weak_coins (datetime DESC, composite_score DESC);
```

#### 5.3.2 索引选择原则
- **查询模式**: 基于实际查询需求设计索引
- **选择性**: 高选择性字段优先索引
- **复合索引**: 常用查询条件组合索引

### 5.4 缓存机制设计

#### 5.4.1 内存缓存策略

**缓存配置：**
```python
class DashboardCache:
    def __init__(self, max_size=1000, ttl=900):  # 15分钟TTL
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key, data):
        if len(self.cache) >= self.max_size:
            # LRU淘汰策略
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        self.cache[key] = (data, time.time())
```

#### 5.4.2 缓存失效策略
- **TTL机制**: 15分钟自动失效
- **事件驱动**: 数据更新时主动失效缓存
- **分层缓存**: 内存缓存 + Redis分布式缓存

### 5.5 手动刷新机制

#### 5.5.1 刷新函数实现
```sql
-- 手动刷新存储过程
CREATE OR REPLACE PROCEDURE manual_refresh_dashboard_views()
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_market_sentiment;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_strong_weak_coins;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_coin_analysis;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_summary_view;
    
    RAISE NOTICE '所有Dashboard物化视图已手动刷新';
END;
$$;
```

#### 5.5.2 使用场景管理

**数据异常场景：**
```python
def check_data_consistency():
    """检查数据一致性，触发手动刷新"""
    latest_data_time = get_latest_data_time()
    view_refresh_time = get_view_refresh_time()
    
    if latest_data_time > view_refresh_time + timedelta(minutes=30):
        # 数据滞后超过30分钟，触发刷新
        manual_refresh_dashboard_views()
        logger.warning("检测到数据滞后，已触发手动刷新")
```

**维护操作场景：**
- **系统升级**: 升级后确保数据最新
- **数据修复**: 修复异常数据后刷新视图
- **性能优化**: 优化索引后重新构建视图

### 5.6 监控与告警机制

#### 5.6.1 刷新状态监控
```sql
-- 监控物化视图刷新状态
SELECT 
    matviewname,
    last_refresh,
    now() - last_refresh as refresh_lag
FROM pg_matviews 
WHERE schemaname = 'public' 
AND matviewname LIKE 'dashboard%';
```

#### 5.6.2 性能指标监控
- **刷新延迟**: 监控刷新完成时间
- **查询性能**: 监控物化视图查询响应时间
- **资源使用**: 监控刷新过程中的资源消耗

#### 5.6.3 告警规则
- **刷新失败**: 连续3次刷新失败触发告警
- **数据滞后**: 数据滞后超过30分钟触发告警
- **性能下降**: 查询响应时间超过阈值触发告警

## 6. 技术实现文件

### 6.1 核心实现文件
- **物化视图定义**: `/backend/dbscripts/dashboard_materialized_views.sql`
- **VE指标计算**: `/backend/indecator/ve_calculator.py`
- **牛熊市指标**: `/backend/indecator/bull_bear.py`
- **HMM模型**: `/backend/indecator/hmm_schedule.py`

### 6.2 数据流程
1. **数据采集**: 从交易所API获取原始数据
2. **指标计算**: 在数据库层面计算技术指标
3. **物化视图**: 创建优化查询性能的物化视图
4. **API接口**: 通过REST API提供数据服务
5. **前端展示**: 在Dashboard页面可视化展示

## 7. 使用建议

### 7.1 交易决策建议
- **多指标验证**: 结合HMM信号与其他技术指标
- **风险管理**: 严格按照仓位建议控制风险
- **时间框架验证**: 同时关注多个时间周期的信号

### 7.2 监控建议
- **定期检查**: 监控模型状态和数据质量
- **参数调整**: 根据市场变化调整模型参数
- **异常处理**: 建立完善的异常检测和处理机制

---
