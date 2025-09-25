"""
解耦后的回测引擎 - 统一负责交易执行逻辑
职责：
1. 接收策略的目标仓位信号
2. 决定是否执行交易（资金检查、冷却期、风控等）
3. 处理所有交易逻辑（滑点、手续费等）
4. 统一的回测框架，支持所有策略
"""

import uuid
import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Protocol
from dataclasses import dataclass, field
from pathlib import Path
import logging
import importlib.util
from ..db import fetch_df, to_sql, get_engine
from ..common import setup_logger_with_file_handler

# 配置回测服务日志记录器
backtest_service_logger = setup_logger_with_file_handler(
    logger_name="backtest_service",
    log_filename="backtest_service.log",
    log_level=logging.INFO,
    mode='w'
)

# 常量定义
STRATEGY_DIR = Path(__file__).resolve().parents[2] / "core" / "strategies"

# 默认回测参数
DEFAULT_BACKTEST_PARAMS = {
    "initial_capital": 1000000.0,    # 初始资金
    "fee_rate": 0.001,               # 手续费率
    "slippage": 0.0002,              # 滑点
    "min_trade_amount": 5000.0,      # 最小交易金额
    "min_trade_qty": 0.01,           # 最小交易数量
    "min_position_change": 0.05,     # 最小仓位变动阈值
    "lot_size": 0.0001,              # 最小交易单位
    "cooldown_bars": 0,              # 交易冷却期（K线数）
    "stop_loss_pct": 0.25,           # 止损百分比
    "take_profit_pct": 0.15,         # 止盈百分比
    "max_position": 1.0,             # 最大仓位比例
    "logging_enabled": True,         # 日志开关
}

@dataclass
class StrategySignal:
    """策略信号数据类"""
    datetime: datetime
    target_position: float           # 目标仓位 (0-1)
    signal_type: str = "normal"      # 信号类型

@dataclass
class TradeRecord:
    """交易记录数据类"""
    run_id: str
    datetime: datetime
    code: str
    side: str
    trade_type: str
    price: float
    qty: float
    amount: float
    fee: float
    avg_price: float
    nav: float
    drawdown: float
    current_qty: float
    current_avg_price: float
    realized_pnl: Optional[float]
    close_price: float
    current_cash: float

@dataclass
class BacktestResult:
    """回测结果数据类"""
    run_id: str
    code: str
    start: str
    end: str
    strategy: str
    params: Dict[str, Any]
    nav: pd.Series
    metrics: Dict[str, float]
    signals: List[StrategySignal]
    grid_levels: List[Dict[str, Any]] = field(default_factory=list)  # 网格级别数据
    grid_parameters: Dict[str, Any] = field(default_factory=dict)  # 网格参数数据

class StrategyInterface(Protocol):
    """策略接口协议"""
    
    def run(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        策略运行接口
        
        Args:
            df: OHLC数据
            params: 策略参数
            
        Returns:
            {
                'signals': List[StrategySignal],  # 必须：目标仓位信号列表
                'auxiliary_data': Dict,           # 可选：辅助数据（网格级别、指标等）
                'alerts': List[str],              # 可选：警告信息
                'strategy_metrics': Dict          # 可选：策略自身的指标
            }
        """
        ...

class BacktestLogger:
    """回测日志管理器"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.logger = setup_logger_with_file_handler(
            logger_name="backtest_engine",
            log_filename="backtest_engine_debug.log",
            log_level=logging.INFO,
            mode='w'
        )
    
    def _safe_format(self, value: Any, format_str: str) -> str:
        """安全格式化数值"""
        if value is None or pd.isna(value) or (isinstance(value, float) and np.isnan(value)):
            return 'N/A'
        try:
            return format_str.format(value)
        except (ValueError, TypeError):
            return str(value)
    
    def log_trade(self, trade: TradeRecord):
        """记录交易详细信息"""
        if not self.enabled:
            return
            
        self.logger.debug(
            f"TRADE: {trade.datetime} | {trade.side.upper()} | "
            f"Price: {self._safe_format(trade.price, '{:.4f}')} | "
            f"Qty: {self._safe_format(trade.qty, '{:.4f}')} | "
            f"Amount: {self._safe_format(trade.amount, '{:.2f}')} | "
            f"Fee: {self._safe_format(trade.fee, '{:.2f}')} | "
            f"Type: {trade.trade_type} | "
            f"NAV: {self._safe_format(trade.nav, '{:.2f}')}"
        )
    
    def log_signal(self, signal: StrategySignal):
        """记录策略信号"""
        if not self.enabled:
            return
            
        self.logger.debug(
            f"SIGNAL: {signal.datetime} | "
            f"Target: {self._safe_format(signal.target_position, '{:.4f}')} | "
            f"Type: {signal.signal_type}"
        )
    
    def info(self, message: str):
        if self.enabled:
            self.logger.info(message)
    
    def error(self, message: str):
        if self.enabled:
            self.logger.error(message)

class PositionManager:
    """仓位管理器 - 只负责执行交易，不决策"""
    
    def __init__(self, initial_cash: float):
        self.cash = initial_cash
        self.initial_capital = initial_cash
        self.current_qty = 0.0
        self.avg_price = 0.0
        self.total_trades = 0
        
    def get_nav(self, current_price: float) -> float:
        """计算当前净值"""
        if pd.isna(current_price) or current_price <= 0:
            return self.cash
        return self.cash + self.current_qty * current_price
    
    def get_current_position_ratio(self, current_price: float) -> float:
        """获取当前仓位比例"""
        nav = self.get_nav(current_price)
        if nav <= 0:
            return 0.0
        return (self.current_qty * current_price) / nav
    
    def can_afford_trade(self, delta_qty: float, price: float, fee_rate: float) -> bool:
        """检查是否有足够资金执行交易"""
        if delta_qty <= 0:  # 卖出或不交易
            return abs(delta_qty) <= self.current_qty + 1e-9
        
        # 买入检查
        required_cash = delta_qty * price * (1 + fee_rate)
        return self.cash >= required_cash
    
    def execute_trade(self, delta_qty: float, price: float, fee_rate: float) -> Tuple[float, Optional[float]]:
        """
        执行交易，返回实际交易费用和已实现盈亏
        
        Args:
            delta_qty: 交易数量（正数买入，负数卖出）
            price: 交易价格
            fee_rate: 手续费率
            
        Returns:
            (actual_fee, realized_pnl)
        """
        if abs(delta_qty) < 1e-9:
            return 0.0, None
        
        amount = abs(delta_qty * price)
        fee = amount * fee_rate
        realized_pnl = None
        pre_trade_avg_price = self.avg_price
        
        if delta_qty > 0:  # 买入
            # 更新平均成本
            total_cost = self.avg_price * self.current_qty + price * delta_qty
            self.current_qty += delta_qty
            self.avg_price = total_cost / self.current_qty if self.current_qty > 0 else 0.0
            self.cash -= (amount + fee)
        else:  # 卖出
            # 计算已实现盈亏
            realized_pnl = (price - pre_trade_avg_price) * abs(delta_qty) - fee
            self.current_qty += delta_qty  # delta_qty是负数
            self.cash += (amount - fee)
            
            # 如果完全平仓，重置平均价格
            if self.current_qty < 1e-9:
                self.current_qty = 0.0
                self.avg_price = 0.0
        
        self.total_trades += 1
        return fee, realized_pnl

class RiskManager:
    """风险管理器 - 决定是否触发风控"""
    
    def __init__(self, stop_loss_pct: float, take_profit_pct: float, max_position: float):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_position = max_position
    
    def check_risk_override(self, current_qty: float, avg_price: float, 
                          current_price: float, target_position: float) -> Tuple[bool, str, float]:
        """
        检查是否需要风控覆盖策略信号
        
        Returns:
            (is_override, override_reason, new_target_position)
        """
        if current_qty <= 0 or avg_price <= 0 or pd.isna(current_price):
            return False, "normal", target_position
        
        profit_pct = (current_price - avg_price) / avg_price
        
        # 止盈检查
        if profit_pct >= self.take_profit_pct:
            return True, "take_profit", target_position * 0.5  # 减半仓位
        
        # 止损检查
        if profit_pct <= -self.stop_loss_pct:
            return True, "stop_loss", 0.0  # 完全平仓
        
        # 最大仓位检查
        if target_position > self.max_position:
            return True, "max_position_limit", self.max_position
        
        return False, "normal", target_position

class TradingDecisionEngine:
    """交易决策引擎 - 决定是否执行交易"""
    
    def __init__(self, params: Dict[str, Any]):
        self.min_trade_amount = float(params.get("min_trade_amount", 5000.0))
        self.min_trade_qty = float(params.get("min_trade_qty", 0.01))
        self.min_position_change = float(params.get("min_position_change", 0.02))
        self.lot_size = float(params.get("lot_size", 0.0))
        self.cooldown_bars = int(params.get("cooldown_bars", 0))
        self.last_trade_bar = -9999
    
    def should_trade(self, signal: StrategySignal, current_position: float, 
                    current_price: float, nav: float, bar_index: int) -> Tuple[bool, str]:
        """
        决定是否应该执行交易
        
        Returns:
            (should_trade, reason)
        """
        target_position = signal.target_position
        position_change = abs(target_position - current_position)
        
        # 检查仓位变动是否足够大
        if position_change < self.min_position_change:
            return False, "position_change_too_small"
        
        # 检查冷却期
        if (bar_index - self.last_trade_bar) <= self.cooldown_bars:
            return False, "cooldown_period"
        
        # 计算交易金额
        target_value = nav * target_position
        current_value = nav * current_position
        trade_amount = abs(target_value - current_value)
        
        # 检查最小交易金额
        if trade_amount < self.min_trade_amount:
            return False, "trade_amount_too_small"
        
        return True, "approved"
    
    def calculate_trade_quantity(self, target_position: float, current_qty: float, 
                               current_price: float, nav: float) -> float:
        """计算实际交易数量"""
        target_value = nav * target_position
        target_qty = target_value / current_price if current_price > 0 else 0.0
        delta_qty = target_qty - current_qty
        
        # 应用lot_size约束
        if self.lot_size > 0 and not pd.isna(delta_qty):
            delta_qty = np.floor(abs(delta_qty) / self.lot_size) * self.lot_size * np.sign(delta_qty)
        
        # 应用最小交易数量约束
        if self.min_trade_qty > 0 and abs(delta_qty) < self.min_trade_qty:
            delta_qty = 0.0
        
        return delta_qty
    
    def update_last_trade_bar(self, bar_index: int):
        """更新最后交易时间"""
        self.last_trade_bar = bar_index

class SlippageCalculator:
    """滑点计算器"""
    
    @staticmethod
    def calculate_dynamic_slippage(row: pd.Series, prev_row: Optional[pd.Series], 
                                 base_slippage: float) -> float:
        """计算动态滑点"""
        if "high" not in row or "low" not in row or pd.isna(row["high"]) or pd.isna(row["low"]):
            return base_slippage
        
        # 计算真实波动率
        high_low = row["high"] - row["low"]
        if prev_row is not None and "close" in prev_row:
            high_close = abs(row["high"] - prev_row["close"])
            low_close = abs(row["low"] - prev_row["close"])
            true_range = max(high_low, high_close, low_close)
        else:
            true_range = high_low
        
        # 波动率因子
        price = row["close"]
        volatility_factor = true_range / price if price > 0 else 0.0
        
        return base_slippage * (1 + volatility_factor * 2.0)

class StrategyLoader:
    """策略加载器"""
    
    @staticmethod
    def load_strategy(strategy_name: str):
        """动态加载策略模块"""
        path = STRATEGY_DIR / f"{strategy_name}.py"
        if not path.exists():
            raise FileNotFoundError(f"策略文件不存在: {path}")
        
        spec = importlib.util.spec_from_file_location(f"strategies.{strategy_name}", str(path))
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载策略模块: {strategy_name}")
        
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

class MetricsCalculator:
    """指标计算器"""
    
    @staticmethod
    def calculate_performance_metrics(nav_list: List[float], initial_capital: float, 
                                    trades: List[TradeRecord]) -> Dict[str, float]:
        """计算性能指标"""
        if not nav_list or len(nav_list) < 2:
            return {}
        
        metrics = {}
        
        # 基础收益指标
        final_capital = nav_list[-1]
        metrics['final_capital'] = final_capital
        metrics['final_return'] = final_capital / initial_capital - 1
        
        # 计算最大回撤
        nav_series = pd.Series(nav_list)
        rolling_max = nav_series.expanding().max()
        drawdown = (nav_series - rolling_max) / rolling_max
        metrics['max_drawdown'] = drawdown.min()
        
        # 夏普率
        returns = nav_series.pct_change().dropna()
        if len(returns) > 1 and returns.std() > 0:
            metrics['sharpe'] = np.sqrt(252) * returns.mean() / returns.std()
        
        # 交易相关指标
        if trades:
            metrics['trade_count'] = len(trades)
            metrics['total_fee'] = sum(t.fee for t in trades)
            
            realized_pnls = [t.realized_pnl for t in trades if t.realized_pnl is not None]
            if realized_pnls:
                metrics['total_profit'] = sum(realized_pnls)
                winning_trades = [pnl for pnl in realized_pnls if pnl > 0]
                metrics['win_rate'] = len(winning_trades) / len(realized_pnls)
                
                if len(winning_trades) > 0 and len(realized_pnls) > len(winning_trades):
                    avg_win = np.mean(winning_trades)
                    losing_trades = [pnl for pnl in realized_pnls if pnl <= 0]
                    avg_loss = abs(np.mean(losing_trades)) if losing_trades else 0
                    metrics['profit_factor'] = avg_win / avg_loss if avg_loss > 0 else float('inf')
        
        return metrics

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, logger: BacktestLogger):
        self.logger = logger
        self.engine = get_engine()
    
    def save_backtest_results(self, result: BacktestResult, trades: List[TradeRecord], 
                            nav_list: List[float], metrics: Dict[str, float]):
        """保存回测结果到数据库"""
        try:
            backtest_service_logger.info(f"开始保存回测结果到数据库: 回测ID={result.run_id}")
            self._save_run_record(result, metrics)
            if trades:
                self._save_trades(trades)
                backtest_service_logger.info(f"回测ID={result.run_id}: 保存了 {len(trades)} 条交易记录")
            if nav_list:
                self._save_equity_curve(result.run_id, result.code, nav_list, result.nav.index)
                backtest_service_logger.info(f"回测ID={result.run_id}: 保存了净值曲线数据")
            if result.grid_levels:
                self._save_grid_levels(result.run_id, result.grid_levels)
                backtest_service_logger.info(f"回测ID={result.run_id}: 保存了网格级别数据")
            backtest_service_logger.info(f"回测ID={result.run_id}: 数据库保存完成")
        except Exception as e:
            backtest_service_logger.error(f"回测ID={result.run_id}: 数据库保存失败: {str(e)}")
            raise
    
    def _save_run_record(self, result: BacktestResult, metrics: Dict[str, float]):
        """保存运行记录"""
        run_data = pd.DataFrame([{
            'run_id': result.run_id,
            'strategy': result.strategy,
            'code': result.code,
            'start_time': result.start,
            'end_time': result.end,
            'interval': result.params.get('interval', '1m'),
            'initial_capital': result.params.get('initial_capital', 100000),
            'final_capital': metrics.get('final_capital'),
            'final_return': metrics.get('final_return'),
            'max_drawdown': metrics.get('max_drawdown'),
            'sharpe': metrics.get('sharpe'),
            'win_rate': metrics.get('win_rate'),
            'trade_count': metrics.get('trade_count'),
            'total_fee': metrics.get('total_fee'),
            'total_profit': metrics.get('total_profit'),
            'paras': json.dumps(result.params)
        }])
        
        run_data.to_sql("runs", con=self.engine, if_exists="append", index=False)
        self.logger.info(f"成功写入runs表: {result.run_id}")
    
    def _save_trades(self, trades: List[TradeRecord]):
        """保存交易记录"""
        trades_data = [{
            "run_id": trade.run_id,
            "datetime": trade.datetime,
            "code": trade.code,
            "side": trade.side,
            "trade_type": trade.trade_type,
            "price": trade.price,
            "qty": trade.qty,
            "amount": trade.amount,
            "fee": trade.fee,
            "avg_price": trade.avg_price,
            "nav": trade.nav,
            "drawdown": trade.drawdown,
            "current_qty": trade.current_qty,
            "current_avg_price": trade.current_avg_price,
            "realized_pnl": trade.realized_pnl,
            "close_price": trade.close_price,
            "current_cash": trade.current_cash,
        } for trade in trades]
        
        trades_df = pd.DataFrame(trades_data)
        trades_df.to_sql("trades", con=self.engine, if_exists="append", index=False)
        self.logger.info(f"成功写入trades表: {len(trades_df)} 条记录")
    
    def _save_equity_curve(self, run_id: str, code: str, nav_list: List[float], 
                          datetime_index: pd.Index):
        """保存净值曲线"""
        equity_df = pd.DataFrame({
            "run_id": run_id,
            "datetime": pd.to_datetime(datetime_index),
            "nav": nav_list,
            "drawdown": pd.Series(nav_list).expanding().max().subtract(pd.Series(nav_list)).div(
                pd.Series(nav_list).expanding().max()).fillna(0)
        })
        equity_df.to_sql("equity_curve", con=self.engine, if_exists="append", index=False)
        self.logger.info(f"成功写入equity_curve: {len(equity_df)} 条记录")
    
    def _save_grid_levels(self, run_id: str, grid_levels: List[Dict[str, Any]]):
        """保存网格级别数据"""
        try:
            # 首先检查grid_levels是否为列表类型
            if not isinstance(grid_levels, list):
                self.logger.warning(f"grid_levels不是列表类型: {type(grid_levels).__name__}")
                return
            
            # 如果列表为空，直接返回
            if not grid_levels:
                return
            
            # 处理网格级别数据
            grid_data = []
            for idx, level in enumerate(grid_levels):
                try:
                    # 检查元素是否为字典且包含price字段
                    if isinstance(level, dict) and 'price' in level:
                        # 确保price是数字类型
                        price = level['price']
                        if isinstance(price, (int, float)):
                            grid_data.append({
                                "run_id": run_id,
                                "level": idx,
                                "name": str(level.get('name', '')) if 'name' in level else '',
                                "price": price
                            })
                        else:
                            # 尝试转换为数字
                            try:
                                grid_data.append({
                                    "run_id": run_id,
                                    "level": idx,
                                    "name": str(level.get('name', '')) if 'name' in level else '',
                                    "price": float(price)
                                })
                            except (ValueError, TypeError):
                                self.logger.warning(f"网格级别价格不是有效数字: {price}")
                except Exception as e:
                    # 记录单个级别处理失败的错误，但继续处理其他级别
                    self.logger.warning(f"处理网格级别 {idx} 失败: {str(e)}")
                    continue
            
            # 如果有有效数据，保存到数据库
            if grid_data:
                try:
                    grid_df = pd.DataFrame(grid_data)
                    grid_df.to_sql("grid_levels", con=self.engine, if_exists="append", index=False)
                    self.logger.info(f"成功写入grid_levels: {len(grid_df)} 条记录")
                except Exception as e:
                    self.logger.error(f"写入grid_levels表失败: {str(e)}")
                    # 这里不抛出异常，避免影响整体回测结果的保存
        except Exception as e:
            # 捕获所有其他异常，确保不会中断回测流程
            self.logger.error(f"保存网格级别数据时发生错误: {str(e)}")
            # 这里不抛出异常，避免影响整体回测结果的保存

class BacktestEngine:
    """解耦后的回测引擎 - 统一的交易执行框架"""
    
    def __init__(self):
        self.logger = None
        self.position_manager = None
        self.risk_manager = None
        self.decision_engine = None
        self.db_manager = None
        
    def run_backtest(self, df: pd.DataFrame, params: Dict[str, Any], strategy_name: str) -> Dict[str, Any]:
        """运行回测的主入口"""
        backtest_id = str(uuid.uuid4())
        backtest_service_logger.info(f"开始回测: ID={backtest_id}, 策略={strategy_name}, 参数={params}")
        
        if df.empty:
            backtest_service_logger.warning(f"回测ID={backtest_id}: 输入数据为空，无法执行回测")
            return {"run_id": backtest_id, "nav": [], "signals": [], "metrics": {}}
        
        # 确保关键列的数据类型正确
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'price', 'amount', 'fee', 'nav', 'drawdown']
        for col in numeric_columns:
            if col in df.columns:
                try:
                    # 确保列是数值类型，并且为float64以提高计算精度
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
                    # 替换NaN值为0
                    df[col] = df[col].fillna(0)
                except Exception as e:
                    backtest_service_logger.warning(f"回测ID={backtest_id}: 转换列 {col} 为float64类型时出错: {str(e)}")
        
        # 合并参数
        merged_params = {**DEFAULT_BACKTEST_PARAMS, **(params or {})}
        
        # 初始化组件
        self._initialize_components(merged_params)
        backtest_service_logger.info(f"回测ID={backtest_id}: 组件初始化完成")
        
        # 运行策略获取信号
        strategy_result = self._run_strategy(df, merged_params, strategy_name)
        backtest_service_logger.info(f"回测ID={backtest_id}: 策略运行完成，生成 {len(strategy_result.get('signals', []))} 个信号")
        
        # 执行回测
        backtest_result = self._execute_backtest(
            df, strategy_result, merged_params, strategy_name, backtest_id
        )
        
        metrics = backtest_result.get('metrics', {})
        backtest_service_logger.info(
            f"回测ID={backtest_id}: 回测完成 | 最终收益={metrics.get('final_return', 0):.2%} | "
            f"最大回撤={metrics.get('max_drawdown', 0):.2%} | 交易次数={metrics.get('trade_count', 0)}"
        )
        
        return backtest_result
    
    def _initialize_components(self, params: Dict[str, Any]):
        """初始化回测组件"""
        self.logger = BacktestLogger(params.get("logging_enabled", True))
        
        initial_capital = float(params.get("initial_capital", 100000.0))
        self.position_manager = PositionManager(initial_capital)
        
        self.risk_manager = RiskManager(
            float(params.get("stop_loss_pct", 0.15)),
            float(params.get("take_profit_pct", 0.25)),
            float(params.get("max_position", 1.0))
        )
        
        self.decision_engine = TradingDecisionEngine(params)
        self.db_manager = DatabaseManager(self.logger)
    
    def _run_strategy(self, df: pd.DataFrame, params: Dict[str, Any], strategy_name: str) -> Dict[str, Any]:
        """运行策略获取信号"""
        # 加载策略
        mod = StrategyLoader.load_strategy(strategy_name)
        
        # 合并策略默认参数
        strategy_default_params = getattr(mod, "DEFAULT_PARAMS", {})
        strategy_params = {**strategy_default_params, **params}
        
        self.logger.info(f"加载策略: {strategy_name}, 标的: {params.get('code', '')}")
        backtest_service_logger.info(f"策略参数: {strategy_params}")
        # 运行策略
        try:
            result = mod.run(df.copy(), strategy_params)
            return result
        except Exception as e:
            self.logger.error(f"策略运行失败: {str(e)}")
            raise
    
    def _execute_backtest(self, df: pd.DataFrame, strategy_result: Dict[str, Any], 
                         params: Dict[str, Any], strategy_name: str, backtest_id: str) -> Dict[str, Any]:
        """执行回测主逻辑"""
        # 提取策略结果
        signals = strategy_result.get('signals', [])
        alerts = strategy_result.get('alerts', [])
        
        # 直接获取网格相关数据，提供默认值确保即使没有返回也不会出错
        grid_levels = strategy_result.get('grid_levels', [])
        grid_parameters = strategy_result.get('grid_parameters', {})
        
        # 确保grid_levels是前端可直接使用的字典列表
        # 增加健壮性检查：只有当grid_levels不为空且是列表类型时才进行处理
        if grid_levels and isinstance(grid_levels, list):
            # 检查第一个元素是否为对象类型（而非字典）
            if grid_levels and not isinstance(grid_levels[0], dict):
                try:
                    # 尝试转换GridLevel对象列表为纯字典列表
                    converted_levels = []
                    for level in grid_levels:
                        if hasattr(level, 'name') and hasattr(level, 'price'):
                            converted_levels.append({
                                'name': getattr(level, 'name', ''),
                                'price': getattr(level, 'price', 0),
                                'type': getattr(level, 'level_type', 'grid') if hasattr(level, 'level_type') else 'grid'
                            })
                    grid_levels = converted_levels
                except Exception as e:
                    # 如果转换失败，记录错误并使用空列表
                    self.logger.warning(f"转换grid_levels失败: {str(e)}")
                    grid_levels = []
        
# 直接使用grid_levels和grid_parameters，不再创建auxiliary_data
        
        backtest_service_logger.info(f"回测ID={backtest_id}: 开始执行回测，数据点数量={len(df)}, 信号数量={len(signals)}")
        
        # 参数
        fee_rate = float(params.get("fee_rate", 0.001))
        base_slippage = float(params.get("slippage", 0.0002))
        code = params.get("code", "")
        
        # 回测数据
        data = df.reset_index(drop=True)
        trades = []
        nav_list = []
        executed_signals = []
        
        # 将信号转换为字典便于查找
        signals_dict = {}
        for signal in signals:
            # 处理信号的datetime，确保能够匹配
            if isinstance(signal, dict):
                signal_dt = pd.to_datetime(signal['datetime'])
                signals_dict[signal_dt] = StrategySignal(
                    datetime=signal_dt,
                    target_position=signal['target_position'],
                    signal_type=signal.get('signal_type', 'normal'),

                )
            else:
                signals_dict[signal.datetime] = signal
        
        # 主循环
        prev_row = None
        for i, row in data.iterrows():
            dt = pd.to_datetime(row["datetime"])
            price = float(row["close"])
            nav = self.position_manager.get_nav(price)
            nav_list.append(nav)
            
            # 获取当前信号
            current_signal = signals_dict.get(dt)
            if current_signal is None:
                prev_row = row
                continue
            
            self.logger.log_signal(current_signal)
            
            # 风控检查
            current_position = self.position_manager.get_current_position_ratio(price)
            
            is_override, override_reason, final_target_position = self.risk_manager.check_risk_override(
                self.position_manager.current_qty, self.position_manager.avg_price, 
                price, current_signal.target_position
            )
            
            if is_override:
                self.logger.info(f"风控覆盖: {override_reason}, 目标仓位: {current_signal.target_position:.4f} -> {final_target_position:.4f}")
                # 创建新的信号对象
                final_signal = StrategySignal(
                    datetime=current_signal.datetime,
                    target_position=final_target_position,
                    signal_type=override_reason
                )
            else:
                final_signal = current_signal
            
            # 交易决策
            should_trade, trade_reason = self.decision_engine.should_trade(
                final_signal, current_position, price, nav, i
            )
            
            if not should_trade:
                self.logger.info(f"跳过交易: {trade_reason}")
                backtest_service_logger.info(
                    f"回测ID={backtest_id}: 跳过交易 | 时间={dt} | 目标仓位={final_signal.target_position:.4f} | 原因={trade_reason}"
                )
                prev_row = row
                continue
            
            # 计算交易数量
            delta_qty = self.decision_engine.calculate_trade_quantity(
                final_signal.target_position, self.position_manager.current_qty, price, nav
            )
            
            if abs(delta_qty) < 1e-9:
                backtest_service_logger.info(
                    f"回测ID={backtest_id}: 跳过交易 | 时间={dt} | 目标仓位={final_signal.target_position:.4f} | 原因=交易量太小"
                )
                prev_row = row
                continue
            
            # 计算滑点
            slippage = SlippageCalculator.calculate_dynamic_slippage(row, prev_row, base_slippage)
            
            # 执行价格
            exec_price = price * (1 + slippage) if delta_qty > 0 else price * (1 - slippage)
            
            # 资金检查
            if not self.position_manager.can_afford_trade(delta_qty, exec_price, fee_rate):
                # 如果资金不足，尝试最大可能的交易量
                if delta_qty > 0:  # 买入时调整到最大可买数量
                    max_qty = self.position_manager.cash / (exec_price * (1 + fee_rate))
                    delta_qty = min(delta_qty, max_qty)
                    if delta_qty < 1e-9:
                        self.logger.info("资金不足，跳过交易")
                        backtest_service_logger.info(
                            f"回测ID={backtest_id}: 跳过交易 | 时间={dt} | 目标仓位={final_signal.target_position:.4f} | 原因=资金不足"
                        )
                        prev_row = row
                        continue

            # 执行交易前确保参数类型正确
            try:
                delta_qty = float(delta_qty)
                exec_price = float(exec_price)
                fee_rate = float(fee_rate)
            except (ValueError, TypeError) as e:
                backtest_service_logger.error(f"回测ID={backtest_id}: 参数类型转换失败: {str(e)}")
                prev_row = row
                continue
                
            # 执行交易
            fee, realized_pnl = self.position_manager.execute_trade(delta_qty, exec_price, fee_rate)
            
            # 更新决策引擎状态
            self.decision_engine.update_last_trade_bar(i)
            
            # 计算回撤
            peak = max(nav_list)
            drawdown = nav / peak - 1 if peak > 0 else 0
            
            # 创建交易记录
            trade = TradeRecord(
                run_id=backtest_id,
                datetime=dt,
                code=code,
                side="buy" if delta_qty > 0 else "sell",
                trade_type=final_signal.signal_type,
                price=exec_price,
                qty=delta_qty,
                amount=abs(delta_qty * exec_price),
                fee=fee,
                avg_price=self.position_manager.avg_price,
                nav=self.position_manager.get_nav(price),
                drawdown=drawdown,
                current_qty=self.position_manager.current_qty,
                current_avg_price=self.position_manager.avg_price,
                realized_pnl=realized_pnl,
                close_price=price,
                current_cash=self.position_manager.cash
            )
            
            trades.append(trade)
            executed_signals.append(final_signal)
            self.logger.log_trade(trade)
            backtest_service_logger.info(
                f"回测ID={backtest_id}: 执行交易 | 时间={trade.datetime} | {trade.side} | "
                f"价格={trade.price:.4f} | 数量={trade.qty:.4f} | 金额={trade.amount:.2f}")
            
            prev_row = row
        
        # 确保nav_list中的值都是浮点数
        try:
            nav_list = [float(nav) for nav in nav_list]
        except (ValueError, TypeError) as e:
            backtest_service_logger.error(f"回测ID={backtest_id}: 转换净值数据为浮点数失败: {str(e)}")
            nav_list = []
        
        # 确保initial_capital是浮点数
        try:
            initial_capital = float(params.get("initial_capital", 100000))
        except (ValueError, TypeError) as e:
            backtest_service_logger.error(f"回测ID={backtest_id}: 转换初始资金为浮点数失败: {str(e)}")
            initial_capital = 100000.0
        
        # 计算指标
        backtest_service_logger.debug(f"开始计算回测指标: 交易数量={len(trades)}, 净值数据点数量={len(nav_list)}")
        metrics = MetricsCalculator.calculate_performance_metrics(
            nav_list, initial_capital, trades
        )
        
        # 构建结果
        nav_series = pd.Series(nav_list, index=pd.Index(data["datetime"], dtype='datetime64[ns]'))
        
        # 创建BacktestResult对象
        result = BacktestResult(
            run_id=backtest_id,
            code=code,
            start=params.get("start", ""),
            end=params.get("end", ""),
            strategy=strategy_name,
            params=params,
            nav=nav_series,
            metrics=metrics,
            signals=executed_signals,
            grid_levels=grid_levels,
            grid_parameters=grid_parameters
        )
        
        backtest_service_logger.info(f"回测ID={backtest_id}: 信号处理完成，生成 {len(trades)} 条交易记录")
        # 保存到数据库
        self.db_manager.save_backtest_results(result, trades, nav_list, metrics)
        
        # 转换signals为Dashboard需要的格式：datetime(string)、side('buy'|'sell')、price(number)和qty(number)
        formatted_signals = []
        for i, signal in enumerate(executed_signals):
            # 尝试查找与信号关联的交易
            corresponding_trade = None
            if i < len(trades):
                corresponding_trade = trades[i]
                
            # 构建符合Dashboard要求的信号结构
            signal_dict = {
                'datetime': signal.datetime.isoformat(),  # 转换为字符串格式
                'side': 'buy' if corresponding_trade and corresponding_trade.side == 'buy' else 'sell',
                'price': float(corresponding_trade.price) if corresponding_trade else 0.0,
                'qty': float(abs(corresponding_trade.qty)) if corresponding_trade else 0.0  # 使用绝对值确保qty为正数
            }
            formatted_signals.append(signal_dict)

        # 直接返回结果
        return {
            "run_id": backtest_id,
            "code": code,
            "start": result.start,
            "end": result.end,
            "strategy": strategy_name,
            "params": params,
            "nav": nav_series,
            "metrics": metrics,
            "signals": formatted_signals,  # 使用格式化后的signals
            "grid_levels": grid_levels,
            "grid_parameters": grid_parameters,
            "alerts": alerts
        }

# 主要对外接口
def run_backtest(df: pd.DataFrame, params: Dict[str, Any], strategy_name: str) -> Dict[str, Any]:
    """运行回测的主入口函数"""
    engine = BacktestEngine()
    return engine.run_backtest(df, params, strategy_name)

def get_backtest_result(backtest_id: str) -> Dict[str, Any]:
    """获取回测结果"""
    try:
        df_m = fetch_df("SELECT metric_name, metric_value FROM metrics WHERE run_id=:rid", rid=backtest_id)
        df_e = fetch_df("SELECT datetime, nav, drawdown FROM equity_curve WHERE run_id=:rid ORDER BY datetime", rid=backtest_id)
        
        # 直接获取网格级别数据
        grid_levels = []
        try:
            df_g = fetch_df("SELECT level, name, price FROM grid_levels WHERE run_id=:rid ORDER BY level", rid=backtest_id)
            if not df_g.empty:
                for _, row in df_g.iterrows():
                    grid_level = {'price': row['price']}
                    if 'name' in row and pd.notna(row['name']):
                        grid_level['name'] = row['name']
                    grid_levels.append(grid_level)
        except Exception:
            pass
        
        # 获取signals数据
        signals = []
        try:
            # 尝试从trades表获取交易数据作为信号数据
            df_t = fetch_df("SELECT datetime, side, price, qty FROM trades WHERE run_id=:rid ORDER BY datetime", rid=backtest_id)
            if not df_t.empty:
                for _, row in df_t.iterrows():
                    signals.append({
                        'datetime': str(row['datetime']),  # 转换为字符串格式
                        'side': row['side'],
                        'price': float(row['price']),
                        'qty': float(abs(row['qty']))  # 使用绝对值确保qty为正数
                    })
        except Exception as e:
            print(f"获取signals数据失败: {e}")
        
        # 构建返回结果 - 直接返回所有数据
        return {
            'metrics': df_m.to_dict(orient='records'),
            'equity': df_e.to_dict(orient='records'),
            'grid_levels': grid_levels,
            'signals': signals  # 添加signals数据
        }
    except Exception as e:
        print(f"获取回测结果失败: {e}")
        # 错误情况下也直接返回所有字段的空列表/默认值
        return {'metrics': [], 'equity': [], 'grid_levels': [], 'signals': []}
        

# 策略独立运行接口（用于信号可视化）
def run_strategy_only(df: pd.DataFrame, params: Dict[str, Any], strategy_name: str) -> Dict[str, Any]:
    """
    仅运行策略生成信号，不执行回测
    用于策略开发和信号可视化
    """
    mod = StrategyLoader.load_strategy(strategy_name)
    strategy_default_params = getattr(mod, "DEFAULT_PARAMS", {})
    strategy_params = {**strategy_default_params, **params}
    
    # 调用策略的run方法
    result = mod.run(df.copy(), strategy_params)
    
    # 确保grid_levels是前端可直接使用的字典列表
    # 增加健壮性检查：处理各种可能的情况
    if 'grid_levels' in result:
        grid_levels = result['grid_levels']
        
        # 检查grid_levels是否为列表
        if isinstance(grid_levels, list):
            # 只有当列表不为空且第一个元素不是字典时才需要转换
            if grid_levels and not isinstance(grid_levels[0], dict):
                try:
                    # 尝试转换GridLevel对象列表为纯字典列表
                    converted_levels = []
                    for level in grid_levels:
                        if hasattr(level, 'name') and hasattr(level, 'price'):
                            converted_levels.append({
                                'name': getattr(level, 'name', ''),
                                'price': getattr(level, 'price', 0),
                                'type': getattr(level, 'level_type', 'grid') if hasattr(level, 'level_type') else 'grid'
                            })
                    result['grid_levels'] = converted_levels
                except Exception as e:
                    # 如果转换失败，记录警告并使用空列表
                    backtest_service_logger.warning(f"转换grid_levels失败: {str(e)}")
                    result['grid_levels'] = []
        else:
            # 如果不是列表，记录警告并使用空列表
            backtest_service_logger.warning(f"grid_levels不是列表类型: {type(grid_levels).__name__}")
            result['grid_levels'] = []
    else:
        # 如果不存在grid_levels键，添加空列表以保持一致性
        result['grid_levels'] = []
        
    # 确保grid_parameters也存在，提供默认空字典
    if 'grid_parameters' not in result:
        result['grid_parameters'] = {}
    
    # 转换signals为Dashboard需要的格式：datetime(string)、side('buy'|'sell')、price(number)和qty(number)
    if 'signals' in result:
        signals = result['signals']
        formatted_signals = []
        
        # 确保signals是列表类型
        if isinstance(signals, list):
            for signal in signals:
                # 尝试从信号对象或字典中获取所需字段
                if isinstance(signal, dict):
                    # 从字典类型的信号中提取数据
                    datetime_str = signal.get('datetime', '')
                    if isinstance(datetime_str, (pd.Timestamp, datetime)):
                        datetime_str = datetime_str.isoformat()
                    elif not isinstance(datetime_str, str):
                        datetime_str = str(datetime_str)
                        
                    # 确定side（买入或卖出）
                    target_position = signal.get('target_position', 0)
                    current_position = signal.get('current_position', 0) if 'current_position' in signal else 0
                    side = 'buy' if target_position > current_position else 'sell'
                    
                    # 获取价格和数量
                    price = float(signal.get('price', 0.0))
                    qty = float(abs(signal.get('qty', 0.0))) if 'qty' in signal else 0.0
                else:
                    # 从对象类型的信号中提取数据
                    datetime_obj = getattr(signal, 'datetime', None)
                    datetime_str = datetime_obj.isoformat() if datetime_obj else ''
                    
                    # 确定side（买入或卖出）
                    target_position = getattr(signal, 'target_position', 0)
                    current_position = getattr(signal, 'current_position', 0) if hasattr(signal, 'current_position') else 0
                    side = 'buy' if target_position > current_position else 'sell'
                    
                    # 获取价格和数量（对于策略生成的信号，可能没有实际的价格和数量，这里使用默认值）
                    price = float(getattr(signal, 'price', 0.0))
                    qty = float(abs(getattr(signal, 'qty', 0.0))) if hasattr(signal, 'qty') else 0.0
                    
                # 构建符合Dashboard要求的信号结构
                formatted_signals.append({
                    'datetime': datetime_str,
                    'side': side,
                    'price': price,
                    'qty': qty
                })
        
        # 更新result中的signals为格式化后的版本
        result['signals'] = formatted_signals
    
    return result