"""
轻量级加密货币量化交易框架
基于VectorBT构建，支持策略管理、回测、参数优化和结果分析
"""

import numpy as np
import pandas as pd
import vectorbt as vbt
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import json
import os
from datetime import datetime
import ccxt
import warnings
warnings.filterwarnings('ignore')


@dataclass
class BacktestConfig:
    """回测配置数据类"""
    symbol: str = 'BTC/USDT'
    exchange: str = 'binance'
    timeframe: str = '1h'
    start_date: str = '2023-01-01'
    end_date: str = '2024-01-01'
    initial_capital: float = 10000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.001    # 0.1%
    
    def to_dict(self):
        return self.__dict__


@dataclass
class StrategyResult:
    """策略回测结果数据类"""
    strategy_name: str
    config: BacktestConfig
    params: Dict[str, Any]
    
    # 性能指标
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    
    # 详细数据
    portfolio: Any = None
    trades: pd.DataFrame = None
    equity_curve: pd.Series = None
    
    def summary(self) -> Dict[str, Any]:
        """返回结果摘要"""
        return {
            'strategy': self.strategy_name,
            'symbol': self.config.symbol,
            'total_return': f"{self.total_return:.2%}",
            'annual_return': f"{self.annual_return:.2%}",
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'max_drawdown': f"{self.max_drawdown:.2%}",
            'win_rate': f"{self.win_rate:.2%}",
            'profit_factor': f"{self.profit_factor:.2f}",
            'total_trades': self.total_trades
        }


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        返回包含 'long' 和 'short' 列的DataFrame
        1 = 开仓, 0 = 持有, -1 = 平仓
        """
        pass
    
    def validate_params(self) -> bool:
        """验证策略参数"""
        return True


class SMACrossStrategy(BaseStrategy):
    """简单移动均线交叉策略"""
    
    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        super().__init__(
            name="SMA_Cross",
            params={'fast_period': fast_period, 'slow_period': slow_period}
        )
        
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成SMA交叉信号"""
        close = data['close']
        
        # 计算移动均线
        sma_fast = close.rolling(window=self.params['fast_period']).mean()
        sma_slow = close.rolling(window=self.params['slow_period']).mean()
        
        # 生成信号
        signals = pd.DataFrame(index=data.index)
        signals['long'] = ((sma_fast > sma_slow) & 
                          (sma_fast.shift(1) <= sma_slow.shift(1))).astype(int)
        signals['short'] = ((sma_fast < sma_slow) & 
                           (sma_fast.shift(1) >= sma_slow.shift(1))).astype(int)
        
        return signals


class RSIMeanReversionStrategy(BaseStrategy):
    """RSI均值回归策略"""
    
    def __init__(self, rsi_period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(
            name="RSI_MeanReversion",
            params={
                'rsi_period': rsi_period,
                'oversold': oversold,
                'overbought': overbought
            }
        )
        
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成RSI均值回归信号"""
        close = data['close']
        
        # 计算RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=self.params['rsi_period']).mean()
        avg_loss = loss.rolling(window=self.params['rsi_period']).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # 生成信号
        signals = pd.DataFrame(index=data.index)
        signals['long'] = ((rsi < self.params['oversold']) & 
                          (rsi.shift(1) >= self.params['oversold'])).astype(int)
        signals['short'] = ((rsi > self.params['overbought']) & 
                           (rsi.shift(1) <= self.params['overbought'])).astype(int)
        
        return signals


class DataManager:
    """数据管理器"""
    
    def __init__(self, cache_dir: str = './data_cache'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
    def fetch_data(self, config: BacktestConfig, use_cache: bool = True) -> pd.DataFrame:
        """获取市场数据"""
        cache_file = f"{self.cache_dir}/{config.exchange}_{config.symbol.replace('/', '_')}_{config.timeframe}_{config.start_date}_{config.end_date}.csv"
        
        # 尝试从缓存加载
        if use_cache and os.path.exists(cache_file):
            print(f"Loading cached data from {cache_file}")
            data = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            return data
            
        # 从交易所获取数据
        print(f"Fetching data from {config.exchange}...")
        try:
            exchange = getattr(ccxt, config.exchange)()
            
            # 获取OHLCV数据
            since = exchange.parse8601(config.start_date + 'T00:00:00Z')
            end = exchange.parse8601(config.end_date + 'T00:00:00Z')
            
            all_candles = []
            while since < end:
                candles = exchange.fetch_ohlcv(
                    config.symbol, 
                    config.timeframe, 
                    since, 
                    limit=1000
                )
                if not candles:
                    break
                all_candles.extend(candles)
                since = candles[-1][0] + 1
                
            # 转换为DataFrame
            data = pd.DataFrame(
                all_candles, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
            data.set_index('timestamp', inplace=True)
            
            # 保存到缓存
            if use_cache:
                data.to_csv(cache_file)
                print(f"Data cached to {cache_file}")
                
            return data
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            # 返回模拟数据用于测试
            return self._generate_mock_data(config)
            
    def _generate_mock_data(self, config: BacktestConfig) -> pd.DataFrame:
        """生成模拟数据用于测试"""
        print("Generating mock data for testing...")
        date_range = pd.date_range(
            start=config.start_date,
            end=config.end_date,
            freq='1h'
        )
        
        # 生成模拟价格数据
        np.random.seed(42)
        returns = np.random.normal(0.0002, 0.02, len(date_range))
        close_prices = 50000 * np.exp(np.cumsum(returns))
        
        data = pd.DataFrame(index=date_range)
        data['close'] = close_prices
        data['open'] = data['close'].shift(1).fillna(close_prices[0])
        data['high'] = data[['open', 'close']].max(axis=1) * (1 + np.abs(np.random.normal(0, 0.005, len(date_range))))
        data['low'] = data[['open', 'close']].min(axis=1) * (1 - np.abs(np.random.normal(0, 0.005, len(date_range))))
        data['volume'] = np.random.uniform(100, 1000, len(date_range))
        
        return data


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, data_manager: DataManager = None):
        self.data_manager = data_manager or DataManager()
        
    def run_backtest(self, 
                    strategy: BaseStrategy, 
                    config: BacktestConfig,
                    data: pd.DataFrame = None) -> StrategyResult:
        """执行单次回测"""
        
        # 获取数据
        if data is None:
            data = self.data_manager.fetch_data(config)
            
        # 生成交易信号
        signals = strategy.generate_signals(data)
        
        # 构建入场和出场信号
        entries = signals['long'].fillna(0).astype(bool)
        exits = signals['short'].fillna(0).astype(bool)
        
        # 使用VectorBT执行回测
        portfolio = vbt.Portfolio.from_signals(
            close=data['close'],
            entries=entries,
            exits=exits,
            init_cash=config.initial_capital,
            fees=config.commission,
            slippage=config.slippage,
            freq='1h'
        )
        
        # 计算性能指标
        result = StrategyResult(
            strategy_name=strategy.name,
            config=config,
            params=strategy.params,
            portfolio=portfolio
        )
        
        # 填充性能指标
        result.total_return = portfolio.total_return()
        result.annual_return = portfolio.annualized_return()
        result.sharpe_ratio = portfolio.sharpe_ratio()
        result.max_drawdown = portfolio.max_drawdown()
        
        trades = portfolio.trades.records_readable
        if len(trades) > 0:
            result.total_trades = len(trades)
            result.win_rate = portfolio.trades.win_rate()
            result.profit_factor = portfolio.trades.profit_factor()
            result.trades = trades
            
        result.equity_curve = portfolio.value()
        
        return result
    
    def optimize_parameters(self,
                          strategy_class: type,
                          param_grid: Dict[str, List[Any]],
                          config: BacktestConfig,
                          metric: str = 'sharpe_ratio') -> Dict[str, Any]:
        """批量回测参数优化"""
        
        # 获取数据（只获取一次）
        data = self.data_manager.fetch_data(config)
        
        # 生成参数组合
        param_combinations = self._generate_param_combinations(param_grid)
        
        results = []
        best_result = None
        best_metric = -np.inf
        
        print(f"Running {len(param_combinations)} parameter combinations...")
        
        for i, params in enumerate(param_combinations):
            # 创建策略实例
            strategy = strategy_class(**params)
            
            # 运行回测
            result = self.run_backtest(strategy, config, data)
            
            # 获取优化指标
            metric_value = getattr(result, metric)
            
            results.append({
                'params': params,
                'metric': metric_value,
                'result': result
            })
            
            # 更新最佳结果
            if metric_value > best_metric:
                best_metric = metric_value
                best_result = result
                
            # 进度显示
            if (i + 1) % 10 == 0:
                print(f"Progress: {i + 1}/{len(param_combinations)}")
                
        # 排序结果
        results.sort(key=lambda x: x['metric'], reverse=True)
        
        return {
            'best_params': results[0]['params'],
            'best_metric': results[0]['metric'],
            'best_result': results[0]['result'],
            'all_results': results[:10]  # 返回前10个最佳结果
        }
        
    def _generate_param_combinations(self, param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """生成参数组合"""
        import itertools
        
        keys = param_grid.keys()
        values = param_grid.values()
        
        combinations = []
        for combination in itertools.product(*values):
            combinations.append(dict(zip(keys, combination)))
            
        return combinations


class ResultAnalyzer:
    """结果分析器"""
    
    @staticmethod
    def compare_strategies(results: List[StrategyResult]) -> pd.DataFrame:
        """比较多个策略结果"""
        comparison_data = []
        
        for result in results:
            comparison_data.append({
                'Strategy': result.strategy_name,
                'Total Return': result.total_return,
                'Annual Return': result.annual_return,
                'Sharpe Ratio': result.sharpe_ratio,
                'Max Drawdown': result.max_drawdown,
                'Win Rate': result.win_rate,
                'Profit Factor': result.profit_factor,
                'Total Trades': result.total_trades
            })
            
        df = pd.DataFrame(comparison_data)
        df = df.sort_values('Sharpe Ratio', ascending=False)
        
        return df
    
    @staticmethod
    def generate_report(result: StrategyResult, save_path: str = None) -> str:
        """生成详细报告"""
        report = []
        report.append("=" * 60)
        report.append(f"STRATEGY BACKTEST REPORT")
        report.append("=" * 60)
        report.append(f"\nStrategy: {result.strategy_name}")
        report.append(f"Symbol: {result.config.symbol}")
        report.append(f"Period: {result.config.start_date} to {result.config.end_date}")
        report.append(f"Initial Capital: ${result.config.initial_capital:,.2f}")
        
        report.append(f"\nStrategy Parameters:")
        for key, value in result.params.items():
            report.append(f"  {key}: {value}")
            
        report.append(f"\nPerformance Metrics:")
        report.append(f"  Total Return: {result.total_return:.2%}")
        report.append(f"  Annual Return: {result.annual_return:.2%}")
        report.append(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        report.append(f"  Max Drawdown: {result.max_drawdown:.2%}")
        report.append(f"  Win Rate: {result.win_rate:.2%}")
        report.append(f"  Profit Factor: {result.profit_factor:.2f}")
        report.append(f"  Total Trades: {result.total_trades}")
        
        if result.portfolio:
            final_value = result.portfolio.final_value()
            report.append(f"  Final Portfolio Value: ${final_value:,.2f}")
            
        report_text = "\n".join(report)
        
        if save_path:
            with open(save_path, 'w') as f:
                f.write(report_text)
                
        return report_text
    
    @staticmethod
    def plot_results(result: StrategyResult):
        """绘制回测结果图表"""
        if result.portfolio is None:
            print("No portfolio data to plot")
            return
            
        # 创建图表
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        
        # 1. 权益曲线
        result.equity_curve.plot(ax=axes[0], title='Equity Curve')
        axes[0].set_ylabel('Portfolio Value ($)')
        axes[0].grid(True, alpha=0.3)
        
        # 2. 回撤
        drawdown = result.portfolio.drawdown()
        drawdown.plot(ax=axes[1], title='Drawdown', color='red')
        axes[1].set_ylabel('Drawdown (%)')
        axes[1].grid(True, alpha=0.3)
        
        # 3. 交易信号
        if result.trades is not None and len(result.trades) > 0:
            trades_df = pd.DataFrame(result.trades)
            trades_df['Exit Timestamp'] = pd.to_datetime(trades_df['Exit Timestamp'])
            trades_df['PnL'] = trades_df['PnL']
            
            # 绘制累计收益
            cumulative_pnl = trades_df['PnL'].cumsum()
            axes[2].plot(trades_df['Exit Timestamp'], cumulative_pnl)
            axes[2].set_title('Cumulative PnL')
            axes[2].set_ylabel('Cumulative PnL ($)')
            axes[2].grid(True, alpha=0.3)
            
        plt.tight_layout()
        plt.show()


class StrategyManager:
    """策略管理器"""
    
    def __init__(self):
        self.strategies = {}
        self.results = []
        self.engine = BacktestEngine()
        self.analyzer = ResultAnalyzer()
        
    def register_strategy(self, strategy: BaseStrategy):
        """注册策略"""
        self.strategies[strategy.name] = strategy
        print(f"Strategy '{strategy.name}' registered")
        
    def list_strategies(self) -> List[str]:
        """列出所有策略"""
        return list(self.strategies.keys())
        
    def run_single_backtest(self, 
                           strategy_name: str, 
                           config: BacktestConfig) -> StrategyResult:
        """运行单个策略回测"""
        if strategy_name not in self.strategies:
            raise ValueError(f"Strategy '{strategy_name}' not found")
            
        strategy = self.strategies[strategy_name]
        result = self.engine.run_backtest(strategy, config)
        self.results.append(result)
        
        return result
        
    def run_all_strategies(self, config: BacktestConfig) -> pd.DataFrame:
        """运行所有策略"""
        results = []
        
        for name, strategy in self.strategies.items():
            print(f"Running {name}...")
            result = self.engine.run_backtest(strategy, config)
            results.append(result)
            
        self.results.extend(results)
        
        # 返回比较结果
        return self.analyzer.compare_strategies(results)
        
    def optimize_strategy(self,
                         strategy_class: type,
                         param_grid: Dict[str, List[Any]],
                         config: BacktestConfig,
                         metric: str = 'sharpe_ratio') -> Dict[str, Any]:
        """优化策略参数"""
        return self.engine.optimize_parameters(
            strategy_class, 
            param_grid, 
            config, 
            metric
        )
        
    def save_results(self, filepath: str):
        """保存所有结果"""
        results_data = []
        
        for result in self.results:
            results_data.append({
                'strategy': result.strategy_name,
                'params': result.params,
                'summary': result.summary()
            })
            
        with open(filepath, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
            
        print(f"Results saved to {filepath}")


# ==================== 使用示例 ====================

def main():
    """主函数 - 演示框架使用"""
    
    # 1. 创建策略管理器
    manager = StrategyManager()
    
    # 2. 注册策略
    manager.register_strategy(SMACrossStrategy(fast_period=10, slow_period=30))
    manager.register_strategy(RSIMeanReversionStrategy(rsi_period=14, oversold=30, overbought=70))
    
    # 3. 配置回测参数
    config = BacktestConfig(
        symbol='BTC/USDT',
        exchange='binance',
        timeframe='1h',
        start_date='2023-01-01',
        end_date='2024-01-01',
        initial_capital=10000,
        commission=0.001
    )
    
    print("\n" + "="*60)
    print("RUNNING SINGLE STRATEGY BACKTEST")
    print("="*60)
    
    # 4. 运行单个策略回测
    result = manager.run_single_backtest('SMA_Cross', config)
    print("\nSingle Backtest Result:")
    print(manager.analyzer.generate_report(result))
    
    print("\n" + "="*60)
    print("RUNNING PARAMETER OPTIMIZATION")
    print("="*60)
    
    # 5. 参数优化
    param_grid = {
        'fast_period': [5, 10, 15, 20],
        'slow_period': [20, 30, 40, 50]
    }
    
    optimization_result = manager.optimize_strategy(
        SMACrossStrategy,
        param_grid,
        config,
        metric='sharpe_ratio'
    )
    
    print(f"\nBest Parameters: {optimization_result['best_params']}")
    print(f"Best Sharpe Ratio: {optimization_result['best_metric']:.2f}")
    
    print("\nTop 5 Parameter Combinations:")
    for i, result in enumerate(optimization_result['all_results'][:5]):
        print(f"{i+1}. Params: {result['params']}, Sharpe: {result['metric']:.2f}")
    
    print("\n" + "="*60)
    print("COMPARING ALL STRATEGIES")
    print("="*60)
    
    # 6. 比较所有策略
    comparison = manager.run_all_strategies(config)
    print("\nStrategy Comparison:")
    print(comparison.to_string())
    
    # 7. 保存结果
    manager.save_results('backtest_results.json')
    
    # 8. 可视化结果（如果需要）
    # manager.analyzer.plot_results(result)


if __name__ == "__main__":
    main()
