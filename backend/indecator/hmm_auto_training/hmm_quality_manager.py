#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HMM模型质量管理和自动重训练系统

功能特性：
1. 多维度模型质量评估
2. 智能重训练决策
3. 性能退化检测
4. 自适应参数调整
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging
import joblib
from dataclasses import dataclass
from enum import Enum

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.logger import LoggerFactory
from hmm_auto_trainer import HMMAutoTrainer

logger = LoggerFactory.get_logger("hmm_quality_manager")

class ModelQualityStatus(Enum):
    """模型质量状态枚举"""
    EXCELLENT = "excellent"  # 优秀
    GOOD = "good"           # 良好
    FAIR = "fair"           # 一般
    POOR = "poor"           # 较差
    FAILED = "failed"       # 失败

@dataclass
class QualityMetrics:
    """质量指标数据类"""
    log_likelihood: float
    state_prob_stability: float
    state_switch_rate: float
    probability_distribution_quality: float
    overall_quality: float
    convergence_score: float
    stability_score: float
    predictive_power: float

@dataclass
class ModelAssessment:
    """模型评估结果"""
    symbol: str
    timeframe: str
    quality_status: ModelQualityStatus
    quality_metrics: QualityMetrics
    assessment_time: datetime
    recommendations: List[str]
    retrain_priority: int  # 重训练优先级 (1-5, 1为最高)

class HMMQualityManager:
    """HMM模型质量管理器"""
    
    def __init__(self):
        self.trainer = HMMAutoTrainer()
        self.assessment_history = {}  # 评估历史记录
        
        # 质量阈值配置
        self.quality_thresholds = {
            'excellent': 0.85,
            'good': 0.70,
            'fair': 0.55,
            'poor': 0.40,
        }
        
        # 重训练策略配置
        self.retrain_strategies = {
            ModelQualityStatus.EXCELLENT: {
                'interval_days': 7,
                'priority': 5
            },
            ModelQualityStatus.GOOD: {
                'interval_days': 3,
                'priority': 4
            },
            ModelQualityStatus.FAIR: {
                'interval_days': 1,
                'priority': 3
            },
            ModelQualityStatus.POOR: {
                'interval_days': 0.5,  # 12小时
                'priority': 2
            },
            ModelQualityStatus.FAILED: {
                'interval_days': 0.1,  # 立即重训练
                'priority': 1
            }
        }
    
    def comprehensive_quality_assessment(self, symbol: str, timeframe: str, 
                                       df_returns: pd.DataFrame) -> ModelAssessment:
        """
        综合质量评估
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            df_returns: 收益率数据
            
        Returns:
            模型评估结果
        """
        try:
            # 加载模型
            model_file = os.path.join(self.trainer.model_dir, 
                                    f"hmm_model_{symbol.replace('/', '_')}_{timeframe}.pkl")
            
            if not os.path.exists(model_file):
                return self._create_failed_assessment(symbol, timeframe, "模型文件不存在")
            
            hmm = joblib.load(model_file)
            
            # 基础质量评估
            base_metrics = self.trainer.evaluate_model_quality(hmm, df_returns)
            
            # 高级质量评估
            advanced_metrics = self._advanced_quality_assessment(hmm, df_returns)
            
            # 综合质量指标
            quality_metrics = QualityMetrics(
                log_likelihood=base_metrics.get('log_likelihood', 0),
                state_prob_stability=base_metrics.get('state_prob_stability', 0),
                state_switch_rate=base_metrics.get('state_switch_rate', 0),
                probability_distribution_quality=base_metrics.get('probability_distribution_quality', 0),
                overall_quality=base_metrics.get('overall_quality', 0),
                convergence_score=advanced_metrics.get('convergence_score', 0),
                stability_score=advanced_metrics.get('stability_score', 0),
                predictive_power=advanced_metrics.get('predictive_power', 0)
            )
            
            # 确定质量状态
            quality_status = self._determine_quality_status(quality_metrics.overall_quality)
            
            # 生成建议
            recommendations = self._generate_recommendations(quality_status, quality_metrics)
            
            # 确定重训练优先级
            retrain_priority = self.retrain_strategies[quality_status]['priority']
            
            assessment = ModelAssessment(
                symbol=symbol,
                timeframe=timeframe,
                quality_status=quality_status,
                quality_metrics=quality_metrics,
                assessment_time=datetime.now(),
                recommendations=recommendations,
                retrain_priority=retrain_priority
            )
            
            # 保存评估记录
            self._save_assessment_record(assessment)
            
            logger.info(f"质量评估完成: {symbol}-{timeframe}, "
                       f"状态={quality_status.value}, 评分={quality_metrics.overall_quality:.3f}")
            
            return assessment
            
        except Exception as e:
            logger.error(f"质量评估失败 {symbol}-{timeframe}: {e}")
            return self._create_failed_assessment(symbol, timeframe, str(e))
    
    def _advanced_quality_assessment(self, hmm, df_returns: pd.DataFrame) -> Dict[str, float]:
        """高级质量评估"""
        try:
            returns_data = df_returns['returns'].values.reshape(-1, 1)
            
            # 1. 收敛性评估
            convergence_score = self._assess_convergence_quality(hmm, returns_data)
            
            # 2. 稳定性评估
            stability_score = self._assess_stability_quality(hmm, returns_data)
            
            # 3. 预测能力评估
            predictive_power = self._assess_predictive_power(hmm, df_returns)
            
            return {
                'convergence_score': convergence_score,
                'stability_score': stability_score,
                'predictive_power': predictive_power
            }
            
        except Exception as e:
            logger.warning(f"高级质量评估失败: {e}")
            return {'convergence_score': 0, 'stability_score': 0, 'predictive_power': 0}
    
    def _assess_convergence_quality(self, hmm, returns_data: np.ndarray) -> float:
        """评估收敛质量"""
        try:
            # 检查模型是否收敛
            if hasattr(hmm, 'converged_') and hmm.converged_:
                convergence_bonus = 0.2
            else:
                convergence_bonus = 0.0
            
            # 检查迭代次数
            if hasattr(hmm, 'n_iter_'):
                max_iter = getattr(hmm, 'n_iter_', 1000)
                if max_iter < 50:  # 迭代次数过少可能未充分收敛
                    convergence_bonus -= 0.1
                elif max_iter > 500:  # 迭代次数过多可能收敛困难
                    convergence_bonus -= 0.05
            
            return max(0, min(1, 0.5 + convergence_bonus))
            
        except Exception as e:
            logger.warning(f"收敛质量评估失败: {e}")
            return 0.5
    
    def _assess_stability_quality(self, hmm, returns_data: np.ndarray) -> float:
        """评估稳定性质量"""
        try:
            # 预测状态概率
            probs = hmm.predict_proba(returns_data)
            
            # 计算状态概率的稳定性
            prob_std = np.std(probs, axis=0)
            avg_prob_std = np.mean(prob_std)
            
            # 稳定性评分 (标准差越小越好)
            stability_score = max(0, 1 - avg_prob_std * 2)
            
            # 检查状态切换的平稳性
            states = hmm.predict(returns_data)
            state_changes = np.diff(states)
            
            # 计算状态切换的平稳性
            if len(state_changes) > 0:
                change_std = np.std(state_changes)
                stability_score *= max(0, 1 - change_std * 0.1)
            
            return max(0, min(1, stability_score))
            
        except Exception as e:
            logger.warning(f"稳定性质量评估失败: {e}")
            return 0.5
    
    def _assess_predictive_power(self, hmm, df_returns: pd.DataFrame) -> float:
        """评估预测能力"""
        try:
            # 使用滚动窗口评估预测能力
            returns_data = df_returns['returns'].values.reshape(-1, 1)
            
            if len(returns_data) < 100:
                return 0.5  # 数据不足，返回中性评分
            
            # 将数据分为训练集和测试集
            split_idx = int(len(returns_data) * 0.7)
            train_data = returns_data[:split_idx]
            test_data = returns_data[split_idx:]
            
            # 在训练集上重新拟合模型（简化评估）
            try:
                # 复制模型结构
                from hmmlearn.hmm import GaussianHMM
                test_hmm = GaussianHMM(n_components=hmm.n_components, 
                                     covariance_type=hmm.covariance_type)
                
                # 使用训练数据拟合
                test_hmm.fit(train_data)
                
                # 计算测试集上的对数似然
                test_score = test_hmm.score(test_data)
                train_score = test_hmm.score(train_data)
                
                # 计算过拟合程度
                overfitting_ratio = abs(test_score - train_score) / abs(train_score)
                
                # 预测能力评分 (过拟合越小越好)
                predictive_power = max(0, 1 - overfitting_ratio * 2)
                
                return max(0, min(1, predictive_power))
                
            except Exception as e:
                logger.warning(f"预测能力评估失败: {e}")
                return 0.5
                
        except Exception as e:
            logger.warning(f"预测能力评估失败: {e}")
            return 0.5
    
    def _determine_quality_status(self, overall_quality: float) -> ModelQualityStatus:
        """确定质量状态"""
        if overall_quality >= self.quality_thresholds['excellent']:
            return ModelQualityStatus.EXCELLENT
        elif overall_quality >= self.quality_thresholds['good']:
            return ModelQualityStatus.GOOD
        elif overall_quality >= self.quality_thresholds['fair']:
            return ModelQualityStatus.FAIR
        elif overall_quality >= self.quality_thresholds['poor']:
            return ModelQualityStatus.POOR
        else:
            return ModelQualityStatus.FAILED
    
    def _generate_recommendations(self, quality_status: ModelQualityStatus, 
                                metrics: QualityMetrics) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if quality_status == ModelQualityStatus.EXCELLENT:
            recommendations.append("模型状态优秀，保持当前训练频率")
            
        elif quality_status == ModelQualityStatus.GOOD:
            recommendations.append("模型状态良好，可适当优化参数")
            if metrics.convergence_score < 0.6:
                recommendations.append("建议增加训练迭代次数")
            
        elif quality_status == ModelQualityStatus.FAIR:
            recommendations.append("模型状态一般，建议优化训练参数")
            if metrics.stability_score < 0.5:
                recommendations.append("模型稳定性不足，建议调整状态数量")
            if metrics.predictive_power < 0.5:
                recommendations.append("预测能力较弱，建议增加训练数据")
            
        elif quality_status == ModelQualityStatus.POOR:
            recommendations.append("模型状态较差，需要立即优化")
            recommendations.append("建议重新选择参数组合")
            recommendations.append("检查数据质量和完整性")
            
        elif quality_status == ModelQualityStatus.FAILED:
            recommendations.append("模型状态失败，需要紧急处理")
            recommendations.append("建议使用保守参数重新训练")
            recommendations.append("检查数据源和模型文件完整性")
        
        # 基于具体指标的额外建议
        if metrics.log_likelihood < -50:
            recommendations.append("对数似然值过低，模型拟合效果不佳")
        
        if metrics.state_switch_rate > 0.3:
            recommendations.append("状态切换过于频繁，可能过拟合")
        
        if metrics.probability_distribution_quality < 0.4:
            recommendations.append("概率分布质量较差，建议检查模型结构")
        
        return recommendations
    
    def _create_failed_assessment(self, symbol: str, timeframe: str, 
                                error_msg: str) -> ModelAssessment:
        """创建失败评估结果"""
        return ModelAssessment(
            symbol=symbol,
            timeframe=timeframe,
            quality_status=ModelQualityStatus.FAILED,
            quality_metrics=QualityMetrics(
                log_likelihood=0,
                state_prob_stability=0,
                state_switch_rate=0,
                probability_distribution_quality=0,
                overall_quality=0,
                convergence_score=0,
                stability_score=0,
                predictive_power=0
            ),
            assessment_time=datetime.now(),
            recommendations=[f"评估失败: {error_msg}", "建议立即检查系统状态"],
            retrain_priority=1
        )
    
    def _save_assessment_record(self, assessment: ModelAssessment):
        """保存评估记录"""
        key = f"{assessment.symbol}-{assessment.timeframe}"
        
        if key not in self.assessment_history:
            self.assessment_history[key] = []
        
        self.assessment_history[key].append(assessment)
        
        # 保留最近100条记录
        if len(self.assessment_history[key]) > 100:
            self.assessment_history[key] = self.assessment_history[key][-100:]
    
    def get_retraining_schedule(self) -> List[Tuple[str, str, int]]:
        """
        获取重训练计划
        
        Returns:
            重训练计划列表 (symbol, timeframe, priority)
        """
        retraining_plan = []
        current_time = datetime.now()
        
        for key, assessments in self.assessment_history.items():
            if not assessments:
                continue
                
            latest_assessment = assessments[-1]
            symbol, timeframe = latest_assessment.symbol, latest_assessment.timeframe
            
            # 检查是否需要重训练
            if self._needs_retraining(latest_assessment, current_time):
                retraining_plan.append((symbol, timeframe, latest_assessment.retrain_priority))
        
        # 按优先级排序
        retraining_plan.sort(key=lambda x: x[2])
        
        return retraining_plan
    
    def _needs_retraining(self, assessment: ModelAssessment, current_time: datetime) -> bool:
        """检查是否需要重训练"""
        # 失败状态立即重训练
        if assessment.quality_status == ModelQualityStatus.FAILED:
            return True
        
        # 检查重训练间隔
        strategy = self.retrain_strategies[assessment.quality_status]
        interval_hours = strategy['interval_days'] * 24
        
        time_since_assessment = (current_time - assessment.assessment_time).total_seconds() / 3600
        
        return time_since_assessment >= interval_hours
    
    def detect_performance_degradation(self, symbol: str, timeframe: str) -> bool:
        """检测性能退化"""
        key = f"{symbol}-{timeframe}"
        
        if key not in self.assessment_history or len(self.assessment_history[key]) < 3:
            return False
        
        assessments = self.assessment_history[key][-5:]  # 最近5次评估
        qualities = [a.quality_metrics.overall_quality for a in assessments]
        
        if len(qualities) < 3:
            return False
        
        # 计算质量趋势
        x = np.arange(len(qualities))
        slope, _ = np.polyfit(x, qualities, 1)
        
        # 如果质量持续下降且斜率小于阈值，则认为性能退化
        degradation_threshold = -0.01  # 每评估周期下降超过1%
        
        return slope < degradation_threshold and all(
            qualities[i] > qualities[i+1] for i in range(len(qualities)-1)
        )
    
    def generate_quality_report(self) -> str:
        """生成质量报告"""
        try:
            report_file = os.path.join(self.trainer.model_dir, 
                                     f"quality_management_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("# HMM模型质量管理报告\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # 统计概览
                status_counts = {status: 0 for status in ModelQualityStatus}
                total_assessments = 0
                
                for key, assessments in self.assessment_history.items():
                    if assessments:
                        latest_status = assessments[-1].quality_status
                        status_counts[latest_status] += 1
                        total_assessments += 1
                
                f.write("## 统计概览\n")
                f.write(f"- 总监控模型数: {len(self.assessment_history)}\n")
                f.write(f"- 总评估次数: {total_assessments}\n")
                
                for status in ModelQualityStatus:
                    count = status_counts[status]
                    if total_assessments > 0:
                        percentage = count / total_assessments * 100
                        f.write(f"- {status.value}: {count} ({percentage:.1f}%)\n")
                
                # 重训练计划
                retraining_plan = self.get_retraining_schedule()
                f.write("\n## 重训练计划\n")
                f.write(f"- 待重训练模型数: {len(retraining_plan)}\n")
                
                for symbol, timeframe, priority in retraining_plan[:10]:  # 显示前10个
                    f.write(f"- {symbol}-{timeframe}: 优先级={priority}\n")
                
                if len(retraining_plan) > 10:
                    f.write(f"- ... 还有 {len(retraining_plan) - 10} 个模型\n")
                
                # 性能退化检测
                f.write("\n## 性能退化检测\n")
                degradation_detected = False
                
                for key in self.assessment_history.keys():
                    symbol, timeframe = key.split('-')
                    if self.detect_performance_degradation(symbol, timeframe):
                        f.write(f"- ⚠️ {key}: 检测到性能退化趋势\n")
                        degradation_detected = True
                
                if not degradation_detected:
                    f.write("- ✅ 未检测到明显的性能退化\n")
            
            logger.info(f"质量管理报告已生成: {report_file}")
            return report_file
            
        except Exception as e:
            logger.error(f"生成质量报告失败: {e}")
            return ""


def main():
    """主函数 - 演示质量管理功能"""
    quality_manager = HMMQualityManager()
    
    # 演示质量评估
    test_symbols = ['BTC/USDT', 'ETH/USDT']
    test_timeframes = ['1h', '4h']
    
    for symbol in test_symbols:
        for timeframe in test_timeframes:
            # 获取测试数据
            df_returns = quality_manager.trainer.get_training_data(symbol, timeframe, lookback_days=1)
            if df_returns is not None:
                assessment = quality_manager.comprehensive_quality_assessment(symbol, timeframe, df_returns)
                
                print(f"\n=== {symbol}-{timeframe} 质量评估 ===")
                print(f"状态: {assessment.quality_status.value}")
                print(f"综合评分: {assessment.quality_metrics.overall_quality:.3f}")
                print(f"重训练优先级: {assessment.retrain_priority}")
                print("建议:")
                for rec in assessment.recommendations:
                    print(f"- {rec}")
    
    # 生成质量报告
    report_file = quality_manager.generate_quality_report()
    if report_file:
        print(f"\n质量报告已生成: {report_file}")


if __name__ == "__main__":
    main()