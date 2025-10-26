#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HMM模型优化实现
包含收敛性检测、数值精度处理、状态稳定性优化等功能
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, List
from hmmlearn.hmm import GaussianHMM
import joblib
import warnings

class HMMModelOptimizer:
    """HMM模型优化器"""
    
    def __init__(self, n_components: int = 2):
        self.n_components = n_components
        self.optimization_config = {
            # 收敛性检测配置
            'convergence': {
                'max_iterations': 1000,
                'tolerance': 1e-5,
                'min_iterations': 50,
                'stability_threshold': 0.01
            },
            # 数值精度配置
            'numerical_stability': {
                'min_covariance': 1e-6,
                'probability_tolerance': 1e-10,
                'normalization_threshold': 1e-8
            },
            # 状态稳定性配置
            'state_stability': {
                'min_state_probability': 0.05,
                'max_state_probability': 0.95,
                'state_switch_threshold': 0.6
            }
        }
    
    def create_optimized_hmm(self, covariance_type: str = 'diag') -> GaussianHMM:
        """
        创建优化配置的HMM模型
        
        Args:
            covariance_type: 协方差矩阵类型
            
        Returns:
            优化配置的HMM模型
        """
        config = self.optimization_config
        
        hmm = GaussianHMM(
            n_components=self.n_components,
            covariance_type=covariance_type,
            n_iter=config['convergence']['max_iterations'],
            tol=config['convergence']['tolerance'],
            min_covar=config['numerical_stability']['min_covariance'],
            init_params='',  # 清空自动初始化，完全手动控制
            random_state=42
        )
        
        return hmm
    
    def initialize_model_parameters(self, hmm: GaussianHMM, data: np.ndarray) -> None:
        """
        智能初始化模型参数
        
        Args:
            hmm: HMM模型
            data: 训练数据
        """
        data_mean = np.mean(data)
        data_std = max(np.std(data), self.optimization_config['numerical_stability']['min_covariance'])
        
        # 根据数据特征动态调整初始化参数
        if data_std < 1e-4:
            # 低波动性数据 - 使用更保守的参数
            hmm.startprob_ = np.array([0.6, 0.4])
            hmm.transmat_ = np.array([[0.95, 0.05], [0.05, 0.95]])
            hmm.means_ = np.array([
                [data_mean - data_std * 0.1],
                [data_mean + data_std * 0.1]
            ])
            hmm.covars_ = np.array([
                [[data_std * 0.5]],
                [[data_std * 0.5]]
            ])
        else:
            # 正常波动性数据
            hmm.startprob_ = np.array([0.5, 0.5])
            hmm.transmat_ = np.array([[0.9, 0.1], [0.1, 0.9]])
            hmm.means_ = np.array([
                [data_mean - data_std * 0.5],
                [data_mean + data_std * 0.5]
            ])
            hmm.covars_ = np.array([
                [data_std * 0.8],
                [data_std * 1.2]
            ])
    
    def train_with_convergence_monitoring(self, hmm: GaussianHMM, data: np.ndarray) -> Dict[str, Any]:
        """
        带收敛性监控的模型训练
        
        Args:
            hmm: HMM模型
            data: 训练数据
            
        Returns:
            训练结果信息
        """
        config = self.optimization_config['convergence']
        
        # 分步训练策略
        training_results = {
            'converged': False,
            'iterations_used': 0,
            'final_log_likelihood': None,
            'state_probability_stability': None,
            'warnings': []
        }
        
        try:
            # 第一步：基础训练（宽松收敛条件）
            hmm.n_iter = config['min_iterations']
            hmm.tol = 1e-2  # 大幅放宽收敛阈值
            hmm.fit(data)
            
            log_likelihood_step1 = hmm.score(data)
            probs_step1 = hmm.predict_proba(data)
            avg_prob_step1 = probs_step1[:, 1].mean()
            
            training_results['iterations_used'] = config['min_iterations']
            
            # 检查第一步训练后的状态概率分布
            if 0.1 <= avg_prob_step1 <= 0.9:
                # 第二步：精细训练（适度收紧收敛条件）
                hmm.n_iter = min(300, config['max_iterations'] - config['min_iterations'])
                hmm.tol = config['tolerance']
                
                # 保存第一步参数作为备份
                backup_params = self._get_model_parameters(hmm)
                
                try:
                    hmm.fit(data)
                    log_likelihood_step2 = hmm.score(data)
                    
                    # 检查是否真正收敛（对数似然应该增加或保持稳定）
                    if log_likelihood_step2 >= log_likelihood_step1 - config['stability_threshold']:
                        training_results['final_log_likelihood'] = log_likelihood_step2
                        training_results['iterations_used'] += hmm.monitor_.iter
                        training_results['converged'] = True
                    else:
                        # 对数似然下降，使用第一步结果
                        self._set_model_parameters(hmm, backup_params)
                        training_results['final_log_likelihood'] = log_likelihood_step1
                        training_results['warnings'].append("模型不收敛，使用第一步训练结果")
                        
                except Exception as e:
                    # 第二步训练失败，使用第一步结果
                    self._set_model_parameters(hmm, backup_params)
                    training_results['final_log_likelihood'] = log_likelihood_step1
                    training_results['warnings'].append(f"第二步训练失败: {e}")
                    
            else:
                training_results['warnings'].append(
                    f"第一步训练后状态概率分布异常: {avg_prob_step1:.3f}"
                )
                
        except Exception as e:
            training_results['warnings'].append(f"训练过程异常: {e}")
            # 使用极简模型作为fallback
            hmm = self._create_fallback_model(data)
            
        # 最终验证模型质量
        if training_results['converged']:
            state_prob_stability = self._check_state_probability_stability(hmm, data)
            training_results['state_probability_stability'] = state_prob_stability
            
            if not state_prob_stability['stable']:
                training_results['warnings'].append("状态概率分布不稳定")
        
        return training_results
    
    def _get_model_parameters(self, hmm: GaussianHMM) -> Dict[str, np.ndarray]:
        """获取模型参数"""
        return {
            'startprob': hmm.startprob_.copy(),
            'transmat': hmm.transmat_.copy(),
            'means': hmm.means_.copy(),
            'covars': hmm.covars_.copy()
        }
    
    def _set_model_parameters(self, hmm: GaussianHMM, params: Dict[str, np.ndarray]) -> None:
        """设置模型参数"""
        hmm.startprob_ = params['startprob']
        hmm.transmat_ = params['transmat']
        hmm.means_ = params['means']
        hmm.covars_ = params['covars']
    
    def _create_fallback_model(self, data: np.ndarray) -> GaussianHMM:
        """创建fallback模型"""
        hmm = GaussianHMM(
            n_components=self.n_components,
            covariance_type='diag',
            n_iter=100,
            tol=1e-2,
            random_state=42
        )
        hmm.fit(data)
        return hmm
    
    def _check_state_probability_stability(self, hmm: GaussianHMM, data: np.ndarray) -> Dict[str, Any]:
        """检查状态概率稳定性"""
        config = self.optimization_config['state_stability']
        
        try:
            probs = hmm.predict_proba(data)
            avg_prob_1 = probs[:, 1].mean()
            
            is_stable = (config['min_state_probability'] <= avg_prob_1 <= 
                        config['max_state_probability'])
            
            return {
                'stable': is_stable,
                'avg_probability': avg_prob_1,
                'min_threshold': config['min_state_probability'],
                'max_threshold': config['max_state_probability']
            }
            
        except Exception as e:
            return {
                'stable': False,
                'error': str(e),
                'avg_probability': None
            }
    
    def normalize_probabilities(self, probabilities: np.ndarray) -> np.ndarray:
        """
        标准化概率矩阵，确保每行和为1
        
        Args:
            probabilities: 概率矩阵
            
        Returns:
            标准化后的概率矩阵
        """
        threshold = self.optimization_config['numerical_stability']['normalization_threshold']
        
        row_sums = probabilities.sum(axis=1)
        
        # 检查是否需要标准化
        needs_normalization = np.any(np.abs(row_sums - 1.0) > threshold)
        
        if needs_normalization:
            # 避免除零
            row_sums[row_sums == 0] = 1.0
            normalized_probs = probabilities / row_sums[:, np.newaxis]
            
            # 确保数值稳定性
            normalized_probs = np.clip(normalized_probs, 0.0, 1.0)
            normalized_probs = normalized_probs / normalized_probs.sum(axis=1, keepdims=True)
            
            return normalized_probs
        else:
            return probabilities
    
    def detect_state_switching(self, state_sequence: List[int], 
                             min_sequence_length: int = 5) -> Dict[str, Any]:
        """
        检测状态切换频率
        
        Args:
            state_sequence: 状态序列
            min_sequence_length: 最小序列长度
            
        Returns:
            状态切换分析结果
        """
        if len(state_sequence) < min_sequence_length:
            return {
                'switch_rate': 0.0,
                'assessment': '数据不足',
                'stable': True
            }
        
        # 计算状态切换次数
        state_changes = np.sum(np.diff(state_sequence) != 0)
        total_periods = len(state_sequence) - 1
        switch_rate = state_changes / total_periods if total_periods > 0 else 0.0
        
        threshold = self.optimization_config['state_stability']['state_switch_threshold']
        is_stable = switch_rate <= threshold
        
        if switch_rate > 0.8:
            assessment = "极度不稳定"
        elif switch_rate > threshold:
            assessment = "切换频繁"
        else:
            assessment = "稳定"
        
        return {
            'switch_rate': switch_rate,
            'assessment': assessment,
            'stable': is_stable,
            'threshold': threshold
        }
    
    def generate_quality_metrics(self, hmm: GaussianHMM, data: np.ndarray, 
                               state_sequence: List[int]) -> Dict[str, Any]:
        """
        生成模型质量指标
        
        Args:
            hmm: 训练好的HMM模型
            data: 训练数据
            state_sequence: 预测的状态序列
            
        Returns:
            质量指标字典
        """
        metrics = {}
        
        try:
            # 对数似然
            metrics['log_likelihood'] = hmm.score(data)
            
            # 状态概率
            probs = hmm.predict_proba(data)
            metrics['avg_state_prob_0'] = probs[:, 0].mean()
            metrics['avg_state_prob_1'] = probs[:, 1].mean()
            
            # 状态切换分析
            switch_analysis = self.detect_state_switching(state_sequence)
            metrics.update(switch_analysis)
            
            # 概率分布稳定性
            prob_stability = self._check_state_probability_stability(hmm, data)
            metrics['state_probability_stable'] = prob_stability['stable']
            
            # 计算信号质量分数
            prob_diff = abs(metrics['avg_state_prob_0'] - metrics['avg_state_prob_1'])
            stability_score = 1.0 - switch_analysis['switch_rate']
            
            metrics['signal_quality'] = (prob_diff * 0.6 + stability_score * 0.4)
            
            # 质量等级分类
            if metrics['signal_quality'] >= 0.8:
                metrics['quality_level'] = 'high'
            elif metrics['signal_quality'] >= 0.6:
                metrics['quality_level'] = 'medium'
            else:
                metrics['quality_level'] = 'low'
                
        except Exception as e:
            metrics['error'] = str(e)
            metrics['signal_quality'] = 0.0
            metrics['quality_level'] = 'error'
        
        return metrics


def test_optimizer():
    """测试优化器功能"""
    optimizer = HMMModelOptimizer()
    
    print("=== HMM模型优化器测试 ===\n")
    
    # 生成测试数据
    np.random.seed(42)
    n_samples = 200
    
    # 创建两个状态的混合数据
    data_state1 = np.random.normal(0.1, 0.5, n_samples//2)
    data_state2 = np.random.normal(-0.1, 0.8, n_samples//2)
    test_data = np.concatenate([data_state1, data_state2])
    test_data = test_data.reshape(-1, 1)
    
    print("1. 创建优化配置的HMM模型")
    hmm = optimizer.create_optimized_hmm()
    print(f"   模型配置: n_iter={hmm.n_iter}, tol={hmm.tol}, min_covar={hmm.min_covar}")
    
    print("\n2. 智能参数初始化")
    optimizer.initialize_model_parameters(hmm, test_data.flatten())
    print(f"   初始转移矩阵:\n{hmm.transmat_}")
    
    print("\n3. 带收敛性监控的训练")
    training_results = optimizer.train_with_convergence_monitoring(hmm, test_data)
    print(f"   训练结果: 收敛={training_results['converged']}, "
          f"迭代次数={training_results['iterations_used']}")
    
    if training_results['warnings']:
        print(f"   警告信息: {training_results['warnings']}")
    
    print("\n4. 生成状态序列和质量指标")
    states = hmm.predict(test_data)
    metrics = optimizer.generate_quality_metrics(hmm, test_data, states.tolist())
    
    print(f"   信号质量: {metrics['signal_quality']:.3f} ({metrics['quality_level']})")
    print(f"   状态切换率: {metrics['switch_rate']:.3f} ({metrics['assessment']})")
    print(f"   平均状态概率: [{metrics['avg_state_prob_0']:.3f}, {metrics['avg_state_prob_1']:.3f}]")
    
    print("\n5. 概率标准化测试")
    test_probs = np.array([[0.6, 0.5], [0.999, 0.001], [0.3, 0.7]])
    normalized_probs = optimizer.normalize_probabilities(test_probs)
    
    for i, (orig, norm) in enumerate(zip(test_probs, normalized_probs)):
        print(f"   原始: {orig} -> 标准化: {norm} (和: {norm.sum():.3f})")


if __name__ == "__main__":
    test_optimizer()