#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全自动HMM模型训练和参数优化系统

功能特性：
1. 自动数据获取和预处理
2. 智能参数优化和模型选择
3. 自动质量评估和重训练
4. 定时调度和监控集成
5. 性能报告和异常告警
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional, Any
import joblib
from sqlalchemy import text
import warnings

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
indecator_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, indecator_dir)
sys.path.insert(0, current_dir)
from common.logger import LoggerFactory
from common.db import get_engine
from hmm_model_optimizer import HMMModelOptimizer
from indecator.hmm_schedule import load_or_train_hmm, generate_signal

logger = LoggerFactory.get_logger("hmm_auto_trainer")

class HMMAutoTrainer:
    """全自动HMM模型训练器"""
    
    def __init__(self, model_dir: Optional[str] = None):
        """
        初始化HMM自动训练器
        
        Args:
            model_dir: 模型保存目录，默认为项目目录backend/indecator/hmmModel/
        """
        self.engine = get_engine()
        self.optimizer = HMMModelOptimizer()
        
        # 设置模型保存目录
        if model_dir:
            self.model_dir = model_dir
        else:
            # 默认目录为项目目录backend/indecator/hmmModel/
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.model_dir = os.path.join(project_root, "indecator", "hmmModel")
        
        os.makedirs(self.model_dir, exist_ok=True)
        logger.info(f"模型保存目录: {self.model_dir}")
        
        # 训练配置
        self.training_config = {
            'data_lookback_days': 30,  # 数据回溯天数
            'min_training_samples': 50,  # 最小训练样本数（降低要求以适应不同时间周期）
            'max_training_samples': 5000,  # 最大训练样本数
            'quality_threshold': 0.7,  # 模型质量阈值
            'retrain_interval_hours': 24,  # 重训练间隔
            'performance_monitoring_window': 7,  # 性能监控窗口
        }
        
        # 参数优化配置
        self.param_config = {
            'n_components_range': [2, 3, 4],  # 隐藏状态数量范围
            'covariance_types': ['diag', 'full', 'spherical', 'tied'],  # 协方差类型
            'max_iterations': 1000,  # 最大迭代次数
            'tolerance': 1e-6,  # 收敛容忍度
        }
    
    def get_training_data(self, symbol: str, timeframe: str, lookback_days: int = 30) -> Optional[pd.DataFrame]:
        """
        获取训练数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            lookback_days: 数据回溯天数
            
        Returns:
            训练数据DataFrame
        """
        try:
            # 根据时间周期确定数据表，支持所有11个时间周期
            table_map = {
                '1m': 'market_ohlcv_1m',
                '3m': 'market_ohlcv_3m',
                '5m': 'market_ohlcv_5m', 
                '15m': 'market_ohlcv_15m',
                '30m': 'market_ohlcv_30m',
                '1h': 'market_ohlcv_1h',
                '2h': 'market_ohlcv_2h',
                '4h': 'market_ohlcv_4h',
                '1d': 'market_ohlcv_1d',
                '2d': 'market_ohlcv_2d',
                '3d': 'market_ohlcv_3d',
            }
            
            table_name = table_map.get(timeframe)
            if not table_name:
                logger.error(f"不支持的时间周期: {timeframe}")
                return None
            
            # 根据表类型确定时间字段
            # 1分钟表使用datetime字段，其他视图使用bucket字段
            if table_name == 'market_ohlcv_1m':
                time_field = 'datetime'
            else:
                time_field = 'bucket'
            
            # 查询K线数据
            query = text(f"""
                SELECT {time_field} as datetime, close, volume
                FROM {table_name}
                WHERE symbol = :symbol
                AND {time_field} >= NOW() - INTERVAL '{lookback_days} day'
                ORDER BY {time_field} ASC
            """)
            
            with self.engine.begin() as conn:
                df = pd.read_sql_query(query, conn, params={'symbol': symbol})
            
            if len(df) < self.training_config['min_training_samples']:
                logger.warning(f"数据量不足: {symbol}-{timeframe} 只有 {len(df)} 条数据")
                return None
            
            # 计算收益率
            df['returns'] = df['close'].pct_change()
            df = df.dropna()
            
            # 限制数据量
            if len(df) > self.training_config['max_training_samples']:
                df = df.tail(self.training_config['max_training_samples'])
            
            logger.info(f"获取到 {symbol}-{timeframe} 训练数据: {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取训练数据失败 {symbol}-{timeframe}: {e}")
            return None
    
    def optimize_hyperparameters(self, df_returns: pd.DataFrame) -> Dict[str, Any]:
        """
        自动优化超参数
        
        Args:
            df_returns: 收益率数据
            
        Returns:
            最优参数配置
        """
        best_params = None
        best_score = -np.inf
        
        returns_data = df_returns['returns'].values.reshape(-1, 1)
        
        # 网格搜索优化参数
        for n_components in self.param_config['n_components_range']:
            for covariance_type in self.param_config['covariance_types']:
                try:
                    # 创建优化器实例
                    optimizer = HMMModelOptimizer(n_components=n_components)
                    
                    # 创建模型
                    hmm = optimizer.create_optimized_hmm(covariance_type=covariance_type)
                    
                    # 智能初始化参数
                    optimizer.initialize_model_parameters(hmm, returns_data.flatten())
                    
                    # 训练模型
                    training_results = optimizer.train_with_convergence_monitoring(hmm, returns_data)
                    
                    if training_results['converged']:
                        # 评估模型质量
                        score = hmm.score(returns_data)
                        
                        # 考虑模型复杂度惩罚
                        complexity_penalty = -0.1 * n_components  # 状态数越多惩罚越大
                        adjusted_score = score + complexity_penalty
                        
                        if adjusted_score > best_score:
                            best_score = adjusted_score
                            best_params = {
                                'n_components': n_components,
                                'covariance_type': covariance_type,
                                'score': score,
                                'training_results': training_results
                            }
                            
                            logger.info(f"发现更优参数: n_components={n_components}, "
                                      f"covariance_type={covariance_type}, score={score:.4f}")
                            
                except Exception as e:
                    logger.warning(f"参数组合失败 n_components={n_components}, "
                                 f"covariance_type={covariance_type}: {e}")
                    continue
        
        if best_params:
            logger.info(f"最优参数: {best_params}")
        else:
            logger.warning("未找到合适的参数组合，使用默认参数")
            best_params = {
                'n_components': 2,
                'covariance_type': 'diag',
                'score': -np.inf
            }
        
        return best_params
    
    def evaluate_model_quality(self, hmm, df_returns: pd.DataFrame) -> Dict[str, float]:
        """
        评估模型质量
        
        Args:
            hmm: 训练好的HMM模型
            df_returns: 收益率数据
            
        Returns:
            质量评估指标
        """
        try:
            returns_data = df_returns['returns'].values.reshape(-1, 1)
            
            # 预测状态概率
            probs = hmm.predict_proba(returns_data)
            states = hmm.predict(returns_data)
            
            # 计算质量指标
            metrics = {}
            
            # 1. 对数似然值
            metrics['log_likelihood'] = hmm.score(returns_data)
            
            # 2. 状态概率稳定性
            state_0_prob_mean = probs[:, 0].mean()
            state_1_prob_mean = probs[:, 1].mean()
            metrics['state_prob_stability'] = 1 - abs(state_0_prob_mean - state_1_prob_mean)
            
            # 3. 状态切换频率
            state_changes = np.diff(states)
            switch_rate = np.sum(state_changes != 0) / len(state_changes)
            metrics['state_switch_rate'] = switch_rate
            
            # 4. 概率分布合理性
            prob_std = np.std(probs, axis=0)
            metrics['probability_distribution_quality'] = 1 - np.mean(prob_std)
            
            # 5. 综合质量评分
            weights = {
                'log_likelihood': 0.3,
                'state_prob_stability': 0.25,
                'state_switch_rate': 0.25,
                'probability_distribution_quality': 0.2
            }
            
            # 标准化各项指标
            normalized_metrics = {}
            for key, value in metrics.items():
                if key == 'log_likelihood':
                    # 对数似然值越大越好，但需要标准化
                    normalized_metrics[key] = max(0, min(1, (value + 100) / 200))
                elif key == 'state_switch_rate':
                    # 切换频率越小越好
                    normalized_metrics[key] = max(0, 1 - value)
                else:
                    normalized_metrics[key] = max(0, min(1, value))
            
            # 计算综合质量评分
            overall_quality = sum(normalized_metrics[key] * weights[key] 
                                for key in weights.keys())
            metrics['overall_quality'] = overall_quality
            
            logger.info(f"模型质量评估: 综合评分={overall_quality:.3f}, "
                       f"对数似然={metrics['log_likelihood']:.3f}, "
                       f"切换频率={switch_rate:.3f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"模型质量评估失败: {e}")
            return {'overall_quality': 0.0}
    
    def auto_train_model(self, symbol: str, timeframe: str, force_retrain: bool = False) -> Dict[str, Any]:
        """
        自动训练模型
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            force_retrain: 是否强制重新训练
            
        Returns:
            训练结果
        """
        model_file = os.path.join(self.model_dir, f"hmm_model_{symbol.replace('/', '_')}_{timeframe}.pkl")
        
        # 检查是否需要重新训练
        if not force_retrain and os.path.exists(model_file):
            # 检查模型文件修改时间
            file_mtime = datetime.fromtimestamp(os.path.getmtime(model_file))
            if datetime.now() - file_mtime < timedelta(hours=self.training_config['retrain_interval_hours']):
                logger.info(f"模型文件较新，跳过训练: {model_file}")
                
                # 加载现有模型并评估质量
                try:
                    hmm = joblib.load(model_file)
                    df_returns = self.get_training_data(symbol, timeframe, lookback_days=7)
                    if df_returns is not None:
                        quality_metrics = self.evaluate_model_quality(hmm, df_returns)
                        
                        if quality_metrics['overall_quality'] >= self.training_config['quality_threshold']:
                            return {
                                'status': 'skipped',
                                'model': hmm,
                                'quality_metrics': quality_metrics,
                                'model_file': model_file
                            }
                        else:
                            logger.warning(f"模型质量不达标 ({quality_metrics['overall_quality']:.3f})，重新训练")
                except Exception as e:
                    logger.warning(f"加载现有模型失败，重新训练: {e}")
        
        # 获取训练数据
        df_returns = self.get_training_data(symbol, timeframe)
        if df_returns is None:
            return {'status': 'failed', 'error': '数据获取失败'}
        
        # 自动优化超参数
        best_params = self.optimize_hyperparameters(df_returns)
        
        # 使用最优参数创建优化器
        optimizer = HMMModelOptimizer(n_components=best_params['n_components'])
        
        try:
            # 创建优化模型
            hmm = optimizer.create_optimized_hmm(covariance_type=best_params['covariance_type'])
            
            # 准备训练数据
            returns_data = df_returns['returns'].values.reshape(-1, 1)
            
            # 智能初始化参数
            optimizer.initialize_model_parameters(hmm, returns_data.flatten())
            
            # 带收敛性监控的训练
            training_results = optimizer.train_with_convergence_monitoring(hmm, returns_data)
            
            # 评估模型质量
            quality_metrics = self.evaluate_model_quality(hmm, df_returns)
            
            # 保存模型
            joblib.dump(hmm, model_file)
            
            result = {
                'status': 'success',
                'model': hmm,
                'quality_metrics': quality_metrics,
                'training_results': training_results,
                'best_params': best_params,
                'model_file': model_file
            }
            
            logger.info(f"模型训练完成: {symbol}-{timeframe}, "
                       f"质量评分={quality_metrics['overall_quality']:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"模型训练失败 {symbol}-{timeframe}: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def batch_train_models(self, symbols: List[str], timeframes: List[str], 
                          max_workers: int = 4) -> Dict[str, Dict]:
        """
        批量训练模型
        
        Args:
            symbols: 交易对列表
            timeframes: 时间周期列表
            max_workers: 最大并行工作数
            
        Returns:
            批量训练结果
        """
        results = {}
        
        # 简单的串行实现（可扩展为并行）
        for symbol in symbols:
            for timeframe in timeframes:
                key = f"{symbol}-{timeframe}"
                logger.info(f"开始训练: {key}")
                
                try:
                    result = self.auto_train_model(symbol, timeframe)
                    results[key] = result
                    
                    if result['status'] == 'success':
                        logger.info(f"训练成功: {key}")
                    elif result['status'] == 'skipped':
                        logger.info(f"跳过训练: {key}")
                    else:
                        logger.error(f"训练失败: {key}, 错误: {result.get('error', '未知错误')}")
                        
                except Exception as e:
                    logger.error(f"训练异常 {key}: {e}")
                    results[key] = {'status': 'failed', 'error': str(e)}
        
        # 生成训练报告
        self.generate_training_report(results)
        
        return results
    
    def generate_training_report(self, results: Dict[str, Dict]) -> str:
        """
        生成训练报告
        
        Args:
            results: 训练结果
            
        Returns:
            报告文件路径
        """
        success_count = sum(1 for r in results.values() if r['status'] == 'success')
        skipped_count = sum(1 for r in results.values() if r['status'] == 'skipped')
        failed_count = sum(1 for r in results.values() if r['status'] == 'failed')
        
        # 计算平均质量评分
        quality_scores = [r.get('quality_metrics', {}).get('overall_quality', 0) 
                         for r in results.values() if r['status'] in ['success', 'skipped']]
        avg_quality = np.mean(quality_scores) if quality_scores else 0
        
        report_content = f"""
# HMM模型自动训练报告

## 训练统计
- 总任务数: {len(results)}
- 成功训练: {success_count}
- 跳过训练: {skipped_count}
- 训练失败: {failed_count}
- 平均质量评分: {avg_quality:.3f}

## 详细结果
"""
        
        for key, result in results.items():
            if result['status'] == 'success':
                quality = result.get('quality_metrics', {}).get('overall_quality', 0)
                report_content += f"- ✅ {key}: 质量评分={quality:.3f}\n"
            elif result['status'] == 'skipped':
                quality = result.get('quality_metrics', {}).get('overall_quality', 0)
                report_content += f"- ⏭️ {key}: 跳过训练 (质量={quality:.3f})\n"
            else:
                error = result.get('error', '未知错误')
                report_content += f"- ❌ {key}: 失败 - {error}\n"
        
        # 保存报告
        report_file = os.path.join(self.model_dir, f"training_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"训练报告已保存: {report_file}")
        return report_file


def main():
    """主函数 - 演示自动训练功能"""
    trainer = HMMAutoTrainer()
    
    # 测试配置
    test_symbols = ['BTC/USDT', 'ETH/USDT']
    test_timeframes = ['1h', '4h']
    
    logger.info("开始自动HMM模型训练...")
    
    # 批量训练模型
    results = trainer.batch_train_models(test_symbols, test_timeframes)
    
    # 统计结果
    success_count = sum(1 for r in results.values() if r['status'] == 'success')
    logger.info(f"自动训练完成: 成功 {success_count}/{len(results)} 个模型")


if __name__ == "__main__":
    main()