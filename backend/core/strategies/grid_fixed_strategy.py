"""
解耦后的固定网格策略 - 纯信号生成器
职责：
1. 只负责生成目标仓位信号
2. 不处理任何交易执行逻辑
3. 可以独立运行用于信号可视化
4. 提供网格级别等辅助数据
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import sys
import os
# 获取项目根目录（当前文件在backend/core/strategies目录下）
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
# 确保项目根目录在Python路径中
if project_root not in sys.path:
    sys.path.append(project_root)
# 从common.py导入setup_logger_with_file_handler函数
from backend.app.common import setup_logger_with_file_handler

# 配置日志记录器
grid_strategy_logger = setup_logger_with_file_handler(
    logger_name="grid_strategy",
    log_filename="grid_strategy.log",
    log_level=logging.INFO,
    mode='w'
)

# 默认策略参数
DEFAULT_PARAMS = {
    "H_price": None,        # 网格最高价
    "L_price": None,        # 网格最低价
    "N": 6,               # 网格数量
    "R": 0.5,              # 最大回撤
    "F": 1000000,          # 总资金
    "atr_window": 14,      # ATR计算窗口
    "per_grid_amount": 100000,   # 每格固定金额
    "stop_loss_price": None,     # 止损价格
}

@dataclass
class GridLevel:
    """网格级别数据类"""
    name: str
    price: float
    level_type: str = "grid"  # grid, stop_loss, take_profit

@dataclass
class GridParameters:
    """网格参数数据类"""
    H_price: float
    L_price: float
    N: int
    D: float              # 网格间距
    grid_points: List[float]
    buy_levels: List[float]
    sell_levels: List[float]
    A: Optional[float] = None      # 每格金额（可选）
    sum_inv: Optional[float] = None # 倒数和（可选）
    
@dataclass
class StrategySignal:
    """策略信号数据类"""
    datetime: datetime
    target_position: float
    signal_type: str = "grid"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class GridBoundsEstimator:
    """网格边界估算器"""
    
    @staticmethod
    def suggest_bounds(df: pd.DataFrame, atr_window: int) -> Optional[Dict[str, float]]:
        """根据历史数据推荐网格边界"""
        if df.empty or len(df) < atr_window:
            return None
        
        # 获取全部数据作为参考期间
        df_ref = df.copy()
        
        # 计算历史极值
        max_price = df_ref['high'].max()
        min_price = df_ref['low'].min()
        
        # 计算ATR
        atr = GridBoundsEstimator._calculate_atr(df_ref, atr_window)
        
        # 扩展边界
        L_price_suggested = max(0.01, min_price - atr * 0.5)  # 向下扩展0.5个ATR
        H_price_suggested = max_price + atr * 0.5            # 向上扩展0.5个ATR
        
        return {
            "historical_high": max_price,
            "historical_low": min_price,
            "atr": atr,
            "suggested_L_price": L_price_suggested,
            "suggested_H_price": H_price_suggested,
            "price_range": max_price - min_price,
            "atr_ratio": atr / ((max_price + min_price) / 2) if max_price + min_price > 0 else 0
        }
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, window: int) -> float:
        """计算平均真实波动率"""
        if len(df) < window:
            return 0.0
            
        try:
            # 尝试使用TA-Lib
            import talib
            atr_values = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=window)
            return atr_values[-1] if not pd.isna(atr_values[-1]) else 0.0
        except ImportError:
            # 手动计算ATR
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift(1))
            low_close = abs(df['low'] - df['close'].shift(1))
            
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(window=window).mean().iloc[-1]
            
            return atr if not pd.isna(atr) else 0.0

class GridParameterCalculator:
    """网格参数计算器"""
    
    @staticmethod
    def calculate_grid_parameters(H_price: float, L_price: float, N: int, 
                                R: float = 0.5, F: float = 10000.0, 
                                explicit_A: Optional[float] = None) -> Tuple[GridParameters, List[str]]:
        """
        计算网格参数
        
        Args:
            H_price: 网格最高价
            L_price: 网格最低价
            N: 网格数量
            R: 资金使用率
            F: 总资金
            explicit_A: 指定的每格金额
            
        Returns:
            (GridParameters, 警告列表)
        """
        alerts = []
        
        # 参数验证
        if L_price >= H_price:
            raise ValueError("L_price必须小于H_price")
        if N <= 0:
            raise ValueError("N必须是正整数")
        if not (0 < R <= 1):
            alerts.append(f"[WARNING] 资金使用率R={R:.2f}不在建议范围(0,1]内")
        
        # 计算网格间距
        D = (H_price - L_price) / N
        
        # 生成网格点
        grid_points = [H_price - i * D for i in range(N + 1)]
        buy_levels = grid_points[1:]    # 买入级别（低价买入）
        sell_levels = grid_points[:-1]  # 卖出级别（高价卖出）
        
        # 计算每格投资金额（如果需要）
        A = None
        sum_inv = None
        
        if explicit_A is not None:
            A = explicit_A
        else:
            # 使用经典网格公式计算
            if len(buy_levels) > 0:
                buy_levels_array = np.array(buy_levels)
                sum_inv = np.sum(1.0 / buy_levels_array)
                denom = N - L_price * sum_inv
                
                if denom > 0:
                    A = (F * R) / denom
                else:
                    alerts.append("[ERROR] 网格参数导致负的每格金额，请调整参数")
                    A = F * R / N  # 简单平均分配
        
        grid_params = GridParameters(
            H_price=H_price,
            L_price=L_price,
            N=N,
            D=D,
            grid_points=grid_points,
            buy_levels=buy_levels,
            sell_levels=sell_levels,
            A=A,
            sum_inv=sum_inv
        )
        
        return grid_params, alerts

class GridSignalGenerator:
    """网格信号生成器 - 核心策略逻辑"""
    
    def __init__(self, grid_params: GridParameters):
        self.grid_params = grid_params
        self.grid_states = {}  # 记录每个网格的状态
        self._initialize_grid_states()
    
    def _initialize_grid_states(self):
        """初始化网格状态"""
        for i, (buy_price, sell_price) in enumerate(zip(self.grid_params.buy_levels, self.grid_params.sell_levels)):
            self.grid_states[i] = {
                'buy_price': buy_price,
                'sell_price': sell_price,
                'is_active': False,      # 是否已激活（买入）
                'target_weight': 1.0 / self.grid_params.N  # 每个网格的目标权重
            }
    
    def generate_signals(self, df: pd.DataFrame) -> List[StrategySignal]:
        """
        生成网格交易信号
        
        Args:
            df: OHLC数据
            
        Returns:
            信号列表
        """
        signals = []
        current_position = 0.0  # 当前总仓位
        
        for _, row in df.iterrows():
            dt = pd.to_datetime(row['datetime'])
            low = row['low']
            high = row['high']
            close = row['close']
            
            # 检查买入信号
            self._check_buy_signals(low, current_position)
            
            # 检查卖出信号
            self._check_sell_signals(high, current_position)
            
            # 计算目标仓位
            target_position = self._calculate_target_position()
            
            # 生成信号（只在仓位变化时）
            if abs(target_position - current_position) > 1e-6:
                active_grids_count = sum(1 for state in self.grid_states.values() if state['is_active'])
                grid_strategy_logger.debug(
                    f"生成信号: 时间={dt}, 当前价格={close:.4f}, "
                    f"目标仓位={target_position:.4f}, 活跃网格数={active_grids_count}"
                )
                signal = StrategySignal(
                    datetime=dt,
                    target_position=target_position,
                    signal_type="grid",
                    metadata={
                        'price': close,
                        'active_grids': active_grids_count,
                        'grid_utilization': target_position
                    }
                )
                signals.append(signal)
                current_position = target_position
        
        return signals
    
    def _check_buy_signals(self, low_price: float, current_position: float):
        """检查买入信号"""
        for grid_id, state in self.grid_states.items():
            if not state['is_active'] and low_price <= state['buy_price']:
                state['is_active'] = True
    
    def _check_sell_signals(self, high_price: float, current_position: float):
        """检查卖出信号"""
        for grid_id, state in self.grid_states.items():
            if state['is_active'] and high_price >= state['sell_price']:
                state['is_active'] = False
    
    def _calculate_target_position(self) -> float:
        """计算目标仓位"""
        active_grids = sum(1 for state in self.grid_states.values() if state['is_active'])
        total_weight = sum(state['target_weight'] for state in self.grid_states.values() if state['is_active'])
        target_position = min(total_weight, 1.0)  # 确保不超过100%仓位
        grid_strategy_logger.debug(
            f"计算目标仓位: 活跃网格数={active_grids}, 总权重={total_weight:.4f}, "
            f"目标仓位={target_position:.4f}"
        )
        return target_position
    
class GridVisualizationHelper:
    """网格可视化辅助工具"""
    
    @staticmethod
    def create_grid_levels(grid_params: GridParameters, stop_loss_price: Optional[float] = None) -> List[GridLevel]:
        """创建网格级别列表用于可视化"""
        levels = []
        
        # 添加网格点
        for i, price in enumerate(grid_params.grid_points):
            levels.append(GridLevel(
                name=f"Grid_{i}",
                price=price,
                level_type="grid"
            ))
        
        # 添加止损线
        if stop_loss_price is not None:
            levels.append(GridLevel(
                name="StopLoss",
                price=stop_loss_price,
                level_type="stop_loss"
            ))
        
        # 按价格排序
        levels.sort(key=lambda x: x.price, reverse=True)
        return levels
    
    @staticmethod
    def calculate_grid_metrics(grid_params: GridParameters) -> Dict[str, float]:
        """计算网格相关指标"""
        metrics = {
            'grid_spacing': grid_params.D,
            'price_range': grid_params.H_price - grid_params.L_price,
            'grid_count': grid_params.N,
            'price_range_pct': (grid_params.H_price - grid_params.L_price) / grid_params.L_price if grid_params.L_price > 0 else 0,
        }
        
        if grid_params.A is not None:
            metrics['per_grid_amount'] = grid_params.A
            metrics['total_investment'] = grid_params.A * grid_params.N
        
        if grid_params.sum_inv is not None:
            metrics['harmonic_mean_price'] = grid_params.N / grid_params.sum_inv
        
        return metrics

def run(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    网格策略主函数 - 纯信号生成
    """
    # 记录策略运行开始
    grid_strategy_logger.info(f"开始运行网格策略，参数: {params}")
    
    # 数据验证
    if df.empty:
        grid_strategy_logger.warning("输入数据为空，无法生成信号")
        return {
            'signals': [],
            'auxiliary_data': {},
            'alerts': ['数据为空'],
            'strategy_metrics': {}
        }
    
    required_columns = ['datetime', 'open', 'high', 'low', 'close']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要列: {missing_columns}")
    
    # 合并参数
    strategy_params = {**DEFAULT_PARAMS, **params}
    
    # 提取参数
    H_price = strategy_params.get('H_price')
    L_price = strategy_params.get('L_price')
    N = int(strategy_params.get('N', 10))
    R = float(strategy_params.get('R', 0.5))
    atr_window = int(strategy_params.get('atr_window', 14))
    per_grid_amount = strategy_params.get('per_grid_amount')
    stop_loss_price = strategy_params.get('stop_loss_price')
    
    alerts = []
    
    # 自动推荐网格边界（如果未提供）
    if H_price is None or L_price is None:
        bounds_info = GridBoundsEstimator.suggest_bounds(df, atr_window)
        if bounds_info is None:
            raise ValueError("无法自动推荐网格边界，请手动设置H_price和L_price")
        
        H_price = bounds_info['suggested_H_price']
        L_price = bounds_info['suggested_L_price']
        alerts.append(f"自动推荐网格边界: H={H_price:.4f}, L={L_price:.4f} (基于ATR={bounds_info['atr']:.4f})")
    
    # 价格合理性检查
    current_price = df['close'].iloc[-1]
    if not (L_price <= current_price <= H_price):
        alerts.append(f"当前价格{current_price:.4f}超出网格范围[{L_price:.4f}, {H_price:.4f}]")
    
    # 计算网格参数
    try:
        grid_strategy_logger.info(f"计算网格参数: H_price={H_price:.4f}, L_price={L_price:.4f}, N={N}, R={R:.2f}")
        grid_params, param_alerts = GridParameterCalculator.calculate_grid_parameters(
            H_price, L_price, N, R, strategy_params.get('F', 10000.0), per_grid_amount
        )
        alerts.extend(param_alerts)
        grid_strategy_logger.info(f"网格参数计算完成: 网格间距={grid_params.D:.4f}, 每格金额={grid_params.A:.2f}")
    except Exception as e:
        alerts.append(f"网格参数计算失败: {str(e)}")
        return {
            'signals': [],
            'grid_levels': [],
            'grid_parameters': {},
            'alerts': alerts
        }
    
    # 生成信号
    try:
        grid_strategy_logger.info(f"开始生成信号，数据点数量: {len(df)}")
        signal_generator = GridSignalGenerator(grid_params)
        signals = signal_generator.generate_signals(df)
    except Exception as e:
        alerts.append(f"信号生成失败: {str(e)}")
        signals = []
    
    # 计算止损价格
    if stop_loss_price is None:
        stop_loss_price = L_price - grid_params.D  # 默认为最低价格下方一个网格间距
    
    # 创建网格级别
    grid_levels = GridVisualizationHelper.create_grid_levels(grid_params, stop_loss_price)
    
    # 获取边界分析数据并合并到网格参数中
    bounds_analysis = GridBoundsEstimator.suggest_bounds(df, atr_window)
    if bounds_analysis:
        # 将边界分析结果合并到grid_params字典中
        grid_params_dict = {
            'H_price': grid_params.H_price,
            'L_price': grid_params.L_price,
            'N': grid_params.N,
            'D': grid_params.D,
            'A': grid_params.A,
            **bounds_analysis
        }
    else:
        grid_params_dict = {
            'H_price': grid_params.H_price,
            'L_price': grid_params.L_price,
            'N': grid_params.N,
            'D': grid_params.D,
            'A': grid_params.A
        }
    
    # 转换信号为字典格式
    signals_dict = []
    for signal in signals:
        signals_dict.append({
            'datetime': signal.datetime.isoformat() if hasattr(signal.datetime, 'isoformat') else str(signal.datetime),
            'target_position': signal.target_position,
            'signal_type': signal.signal_type,
            'metadata': signal.metadata
        })
    
    grid_strategy_logger.info(f"策略运行完成，共生成 {len(signals_dict)} 个信号")
    grid_strategy_logger.info(f"网格参数: {grid_params_dict}")
    grid_strategy_logger.info(f"网格级别: {grid_levels}")
    grid_strategy_logger.info(f"警告信息: {alerts}")

    return {
        'signals': signals_dict,
        'grid_levels': grid_levels,
        'grid_parameters': grid_params_dict,
        'alerts': alerts
    }

def analyze_strategy(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    策略分析函数 - 用于策略开发和调试
    返回更详细的分析结果，包括信号统计、网格利用率等
    """
    result = run(df, params)
    
    if not result['signals']:
        return result
    
    signals = result['signals']
    
    # 信号统计分析
    position_changes = []
    prev_position = 0.0
    
    for signal in signals:
        current_position = signal['target_position']
        position_changes.append(abs(current_position - prev_position))
        prev_position = current_position
    
    # 扩展策略指标
    analysis_metrics = {
        'total_position_changes': len(position_changes),
        'avg_position_change': np.mean(position_changes) if position_changes else 0.0,
        'max_position_change': max(position_changes) if position_changes else 0.0,
        'final_position': signals[-1]['target_position'] if signals else 0.0,
        'max_position_reached': max(s['target_position'] for s in signals) if signals else 0.0,
        'position_utilization': np.mean([s['target_position'] for s in signals]) if signals else 0.0,
    }
    
    result['strategy_metrics'].update(analysis_metrics)
    grid_strategy_logger.info(f"策略指标: {result['strategy_metrics']}")

    result['analysis_data'] = {
        'position_timeline': [(s['datetime'], s['target_position']) for s in signals],
        'position_changes': position_changes
    }
    grid_strategy_logger.info(f"分析数据: {result.get('analysis_data', {})}")
    
    return result

# 便利函数：仅用于快速测试和可视化
def quick_backtest_preview(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """
    快速回测预览 - 返回带有仓位信号的DataFrame
    仅用于策略开发阶段的快速预览，不进行完整回测
    """
    result = run(df, params)
    
    # 创建信号字典
    signals_dict = {}
    for signal in result['signals']:
        dt = pd.to_datetime(signal['datetime'])
        signals_dict[dt] = signal['target_position']
    
    # 合并到原始数据
    df_result = df.copy()
    df_result['datetime'] = pd.to_datetime(df_result['datetime'])
    df_result['target_position'] = df_result['datetime'].map(signals_dict).fillna(method='ffill').fillna(0.0)
    grid_strategy_logger.info(f"快速回测预览完成，共生成 {len(result['signals'])} 个信号")

    return df_result