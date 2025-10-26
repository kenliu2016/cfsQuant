# HMM监控系统操作指导手册

## 📋 系统概述

HMM（隐马尔可夫模型）监控系统是一个完整的量化交易监控解决方案，能够自动监控HMM模型状态、检测异常并生成详细报告。

### 系统架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  数据监控模块    │───▶│  HMM模型训练器   │───▶│  异常检测引擎    │
│                 │    │                 │    │                 │
│ • 数据库连接     │    │ • 模型加载/训练  │    │ • 概率异常检测   │
│ • 数据获取       │    │ • 参数优化       │    │ • 状态切换检测   │
│ • 数据预处理     │    │ • 质量验证       │    │ • 信号质量评估   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  报告生成模块    │◄───│  监控调度器      │◄───│  实时监控器      │
│                 │    │                 │    │                 │
│ • HTML报告      │    │ • 定时执行       │    │ • 持续监控       │
│ • 异常统计       │    │ • 资源管理       │    │ • 实时告警       │
│ • 可视化图表     │    │ • 错误处理       │    │ • 状态跟踪       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 快速开始

### 1. 环境准备
确保系统已安装以下依赖：
```bash
# 检查Python环境
python --version  # 需要Python 3.8+

# 安装依赖包
pip install -r requirements.txt
```

### 2. 数据库配置
确保PostgreSQL数据库正常运行，并已配置正确的连接信息：
```bash
# 检查数据库连接
psql -h localhost -U postgres -d cfsquant
```

## 📊 数据监控操作

### 1. 手动运行监控系统
```bash
cd /Users/aaronkliu/Documents/project/cfsQuant/backend
python hmm_monitoring_system.py
```

**预期输出：**
```
2025-10-27 00:13:48,926 - INFO - 开始HMM模型监控
2025-10-27 00:13:53,958 - INFO - 数据库连接成功
2025-10-27 00:13:54,321 - INFO - 获取到5046条HMM数据
2025-10-27 00:13:54,903 - INFO - 检测到2104个异常
2025-10-27 00:13:54,922 - INFO - 监控报告已保存: hmm_monitoring_report_20251027_001354.html
2025-10-27 00:13:54,924 - INFO - 监控完成: 检测到2104个异常
```

### 2. 监控参数配置
编辑 `hmm_monitoring_system.py` 文件调整监控参数：

```python
# 监控时间范围（小时）
HOURS_TO_MONITOR = 24

# 异常检测阈值
PROBABILITY_THRESHOLD = 0.9  # 概率阈值
STATE_SWITCH_THRESHOLD = 10  # 状态切换频率阈值
```

### 3. 实时监控模式
启用持续监控模式（需要手动配置定时任务）：
```bash
# 每6小时执行一次监控
0 */6 * * * cd /Users/aaronkliu/Documents/project/cfsQuant/backend && python hmm_monitoring_system.py
```

## 🧠 HMM模型训练操作

### 1. 手动训练模型
```python
# 测试模型训练流程
cd /Users/aaronkliu/Documents/project/cfsQuant/backend
python -c "
import numpy as np
from indecator.hmm_schedule import load_or_train_hmm

# 创建测试数据
df_returns = np.random.randn(1000, 1) * 0.01
model_file = 'test_model.pkl'

# 训练模型
model, metrics = load_or_train_hmm(df_returns, model_file)
print(f'模型训练成功: {type(model)}')
print(f'状态数: {model.n_components}')
print(f'训练指标: {metrics}')
"
```

### 2. 模型训练参数优化
编辑 `hmm_model_optimizer.py` 调整训练参数：

```python
# 模型配置
N_COMPONENTS = 2  # 隐藏状态数量
COVARIANCE_TYPE = 'diag'  # 协方差类型
TOLERANCE = 1e-6  # 收敛容忍度
MAX_ITERATIONS = 1000  # 最大迭代次数
```

### 3. 模型质量验证
系统自动执行以下质量检查：
- ✅ 状态概率分布合理性
- ✅ 模型收敛性验证
- ✅ 状态切换频率检测
- ✅ 概率稳定性检查

## 📈 报告生成与分析

### 1. 查看监控报告
监控系统生成的HTML报告包含：

**报告位置：**
```bash
ls -la hmm_monitoring_report_*.html
# 示例: hmm_monitoring_report_20251027_001354.html (18,981行)
```

**报告内容结构：**
```html
<!-- 1. 系统概览 -->
<div class="header">
    <h1>HMM模型监控报告</h1>
    <p>生成时间: 2025-10-27 00:13:54</p>
    <p>数据范围: 最近24小时</p>
</div>

<!-- 2. 关键指标 -->
<div class="metrics">
    <h2>监控指标统计</h2>
    <table>
        <tr><th>指标</th><th>数值</th></tr>
        <tr><td>总数据量</td><td>5046条</td></tr>
        <tr><td>异常数量</td><td>2104个</td></tr>
        <tr><td>异常比例</td><td>41.7%</td></tr>
    </table>
</div>

<!-- 3. 异常详情 -->
<div class="anomalies">
    <h2>异常检测结果</h2>
    <div class="anomaly error">
        <strong>ZKC/USDT - 30m</strong><br>
        时间: 2025-10-27 00:01:42.139215<br>
        异常类型: 极端概率值<br>
        信号质量: nan, 置信度: nan, 概率差异: nan
    </div>
</div>
```

### 2. 异常类型说明
系统检测的异常类型包括：

| 异常类型 | 描述 | 严重程度 | 处理建议 |
|---------|------|----------|----------|
| 极端概率值 | state_prob_0或state_prob_1接近0或1 | 高 | 检查数据质量，重新训练模型 |
| 状态频繁切换 | 短时间内状态切换次数过多 | 中 | 调整模型参数，增加平滑处理 |
| 信号质量异常 | 信号生成逻辑异常 | 高 | 检查信号生成算法 |
| 置信度过低 | 模型预测置信度不足 | 低 | 增加训练数据量 |

### 3. 报告自定义
编辑 `hmm_monitoring_system.py` 中的报告生成函数：

```python
def generate_monitoring_report(self, anomalies, total_count):
    """生成监控报告"""
    # 自定义报告模板
    report_template = """
    <div class="custom-section">
        <h3>自定义分析</h3>
        <p>异常分布分析...</p>
    </div>
    """
```

## ⚙️ 系统配置与管理

### 1. 数据库连接配置
编辑 `common/db.py` 配置数据库连接：

```python
# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'cfsquant',
    'user': 'postgres',
    'password': 'your_password'
}
```

### 2. 日志配置
系统日志文件位置：
```bash
# 查看监控日志
tail -f /Users/aaronkliu/Documents/project/cfsQuant/logs/hmm_monitoring.log

# 查看训练日志
tail -f /Users/aaronkliu/Documents/project/cfsQuant/logs/hmm_training.log
```

### 3. 性能优化建议

**内存优化：**
```python
# 分批处理大数据量
BATCH_SIZE = 1000  # 每批处理的数据量
```

**计算优化：**
```python
# 启用并行计算
import multiprocessing
N_JOBS = multiprocessing.cpu_count() - 1
```

## 🔧 故障排除

### 常见问题及解决方案

**问题1：数据库连接失败**
```bash
# 检查数据库服务
sudo systemctl status postgresql

# 检查连接配置
cat common/db.py | grep -A 10 "DB_CONFIG"
```

**问题2：模型训练失败**
```bash
# 检查数据质量
python -c "
import pandas as pd
from common.db import get_db_connection
conn = get_db_connection()
df = pd.read_sql_query('SELECT * FROM hmm_signals LIMIT 10', conn)
print('数据样本:')
print(df.head())
print('数据统计:')
print(df.describe())
"
```

**问题3：监控报告生成失败**
```bash
# 检查文件权限
ls -la hmm_monitoring_report_*.html

# 检查磁盘空间
df -h /Users/aaronkliu/Documents/project/cfsQuant/backend
```

### 性能监控命令

```bash
# 监控系统资源使用
htop  # 查看CPU和内存使用

# 监控数据库性能
psql -c "SELECT schemaname, relname, n_live_tup, n_dead_tup FROM pg_stat_user_tables;"

# 监控日志文件大小
du -sh /Users/aaronkliu/Documents/project/cfsQuant/logs/*.log
```

## 📋 最佳实践

### 1. 监控频率建议
- **生产环境**: 每6小时执行一次监控
- **测试环境**: 每天执行一次监控
- **开发环境**: 按需手动执行

### 2. 数据质量检查
在执行监控前，建议先检查数据质量：
```python
# 数据质量检查脚本
from common.db import get_db_connection
import pandas as pd

def check_data_quality():
    conn = get_db_connection()
    query = """
    SELECT 
        COUNT(*) as total_count,
        COUNT(DISTINCT symbol) as symbol_count,
        MIN(datetime) as earliest_date,
        MAX(datetime) as latest_date
    FROM hmm_signals
    WHERE datetime >= NOW() - INTERVAL '24 hours'
    """
    df = pd.read_sql_query(query, conn)
    return df
```

### 3. 模型更新策略
- 每周更新一次模型参数
- 每月重新训练基础模型
- 根据市场波动性调整监控阈值

## 🎯 高级功能

### 1. 自定义异常检测规则
```python
# 在hmm_monitoring_system.py中添加自定义规则
def custom_anomaly_detection(row, threshold=0.95):
    """自定义异常检测规则"""
    anomalies = []
    
    # 自定义概率异常检测
    if max(row['state_prob_0'], row['state_prob_1']) > threshold:
        anomalies.append('极端概率值')
    
    # 自定义状态切换检测
    if row.get('state_switch_count', 0) > 5:
        anomalies.append('频繁状态切换')
    
    return anomalies
```

### 2. 多时间周期分析
系统支持多个时间周期的HMM分析：
- **高频**: 1m, 5m, 15m, 30m (每30分钟执行)
- **中频**: 1h, 2h, 4h (每2小时执行)
- **低频**: 1d, 2d, 3d, 3m (每天执行)

### 3. 集成其他指标
可以将HMM监控与其他技术指标结合：
```python
# 集成RSI指标
def integrate_with_rsi(hmm_data, rsi_data):
    """结合RSI指标进行综合分析"""
    # 实现指标集成逻辑
    pass
```

## 📞 技术支持

如遇问题，请参考以下资源：
- 📖 [HMM技术文档](docs/hmm.md)
- ⏰ [定时任务配置](docs/schedule.md)
- 🐛 [问题反馈] GitHub Issues
- 💬 [技术交流] 项目讨论区

---

**文档版本**: 1.0  
**最后更新**: 2025-10-27  
**维护者**: HMM监控系统开发团队