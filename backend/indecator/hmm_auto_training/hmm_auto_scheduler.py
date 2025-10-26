#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HMM模型全自动训练调度器

功能特性：
1. 定时自动训练和参数优化
2. 智能监控和告警
3. 性能追踪和报告生成
4. 异常处理和自动恢复
"""

import os
import sys
import time
import schedule
import threading
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.logger import LoggerFactory
from common.db import get_engine
from hmm_auto_trainer import HMMAutoTrainer

logger = LoggerFactory.get_logger("hmm_auto_scheduler")

class HMMAutoScheduler:
    """全自动HMM模型训练调度器"""
    
    def __init__(self):
        self.trainer = HMMAutoTrainer()
        self.engine = get_engine()
        self.is_running = False
        self.scheduler_thread = None
        
        # 调度配置
        self.schedule_config = {
            'daily_training_time': '02:00',  # 每日训练时间
            'quality_check_interval_hours': 6,  # 质量检查间隔
            'performance_monitoring_interval_hours': 1,  # 性能监控间隔
            'report_generation_time': '08:00',  # 报告生成时间
        }
        
        # 监控配置
        self.monitoring_config = {
            'quality_threshold': 0.6,  # 质量告警阈值
            'performance_degradation_threshold': 0.1,  # 性能下降阈值
            'max_consecutive_failures': 3,  # 最大连续失败次数
        }
        
        # 性能追踪数据
        self.performance_history = {}
        self.failure_counts = {}
        
    def get_active_symbols_timeframes(self) -> List[Dict[str, str]]:
        """
        获取需要监控的交易对和时间周期
        
        Returns:
            交易对和时间周期列表
        """
        try:
            # 查询HMM表中活跃的交易对
            query = """
                SELECT DISTINCT symbol, timeframe
                FROM hmm
                WHERE datetime >= NOW() - INTERVAL '7 days'
                ORDER BY symbol, timeframe
            """
            
            with self.engine.begin() as conn:
                df = pd.read_sql_query(query, conn)
            
            if len(df) == 0:
                # 如果没有活跃数据，使用默认配置
                default_config = [
                    {'symbol': 'BTC/USDT', 'timeframe': '1h'},
                    {'symbol': 'ETH/USDT', 'timeframe': '1h'},
                    {'symbol': 'BTC/USDT', 'timeframe': '4h'},
                    {'symbol': 'ETH/USDT', 'timeframe': '4h'},
                ]
                logger.info("使用默认交易对配置")
                return default_config
            
            # 转换为字典列表
            symbols_timeframes = []
            for _, row in df.iterrows():
                symbols_timeframes.append({
                    'symbol': row['symbol'],
                    'timeframe': row['timeframe']
                })
            
            logger.info(f"获取到 {len(symbols_timeframes)} 个活跃交易对配置")
            return symbols_timeframes
            
        except Exception as e:
            logger.error(f"获取活跃交易对失败: {e}")
            return []
    
    def daily_training_job(self):
        """每日定时训练任务"""
        logger.info("开始执行每日定时训练任务...")
        
        try:
            # 获取活跃交易对
            symbols_timeframes = self.get_active_symbols_timeframes()
            
            if not symbols_timeframes:
                logger.warning("没有找到活跃交易对，跳过训练")
                return
            
            # 提取唯一的交易对和时间周期
            symbols = list(set(st['symbol'] for st in symbols_timeframes))
            timeframes = list(set(st['timeframe'] for st in symbols_timeframes))
            
            # 批量训练模型
            results = self.trainer.batch_train_models(symbols, timeframes)
            
            # 更新性能历史
            self.update_performance_history(results)
            
            # 检查是否需要告警
            self.check_quality_alerts(results)
            
            logger.info("每日定时训练任务完成")
            
        except Exception as e:
            logger.error(f"每日训练任务执行失败: {e}")
            self.handle_training_failure("daily_training", e)
    
    def quality_check_job(self):
        """质量检查任务"""
        logger.info("开始执行质量检查任务...")
        
        try:
            symbols_timeframes = self.get_active_symbols_timeframes()
            
            quality_results = {}
            for st in symbols_timeframes:
                symbol, timeframe = st['symbol'], st['timeframe']
                key = f"{symbol}-{timeframe}"
                
                try:
                    # 获取最新数据评估模型质量
                    df_returns = self.trainer.get_training_data(symbol, timeframe, lookback_days=1)
                    if df_returns is not None:
                        # 加载模型
                        model_file = os.path.join(self.trainer.model_dir, 
                                                 f"hmm_model_{symbol.replace('/', '_')}_{timeframe}.pkl")
                        
                        if os.path.exists(model_file):
                            import joblib
                            hmm = joblib.load(model_file)
                            
                            # 评估质量
                            quality_metrics = self.trainer.evaluate_model_quality(hmm, df_returns)
                            quality_results[key] = quality_metrics
                            
                            # 记录质量变化
                            self.track_quality_change(key, quality_metrics['overall_quality'])
                            
                except Exception as e:
                    logger.warning(f"质量检查失败 {key}: {e}")
                    quality_results[key] = {'overall_quality': 0.0, 'error': str(e)}
            
            # 生成质量报告
            self.generate_quality_report(quality_results)
            
            logger.info("质量检查任务完成")
            
        except Exception as e:
            logger.error(f"质量检查任务执行失败: {e}")
    
    def performance_monitoring_job(self):
        """性能监控任务"""
        logger.info("开始执行性能监控任务...")
        
        try:
            # 检查模型文件状态
            model_files = [f for f in os.listdir(self.trainer.model_dir) 
                          if f.startswith("hmm_model_") and f.endswith(".pkl")]
            
            monitoring_results = {}
            for model_file in model_files:
                try:
                    file_path = os.path.join(self.trainer.model_dir, model_file)
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    file_age_hours = (datetime.now() - file_mtime).total_seconds() / 3600
                    
                    file_size = os.path.getsize(file_path)
                    
                    monitoring_results[model_file] = {
                        'file_age_hours': file_age_hours,
                        'file_size_kb': file_size / 1024,
                        'last_modified': file_mtime.strftime('%Y-%m-%d %H:%M:%S'),
                        'status': 'healthy' if file_age_hours < 48 else 'stale'
                    }
                    
                except Exception as e:
                    monitoring_results[model_file] = {
                        'status': 'error',
                        'error': str(e)
                    }
            
            # 检查系统资源
            system_status = self.check_system_resources()
            monitoring_results['system'] = system_status
            
            # 生成监控报告
            self.generate_monitoring_report(monitoring_results)
            
            logger.info("性能监控任务完成")
            
        except Exception as e:
            logger.error(f"性能监控任务执行失败: {e}")
    
    def report_generation_job(self):
        """报告生成任务"""
        logger.info("开始执行报告生成任务...")
        
        try:
            # 生成综合报告
            self.generate_comprehensive_report()
            logger.info("报告生成任务完成")
            
        except Exception as e:
            logger.error(f"报告生成任务执行失败: {e}")
    
    def update_performance_history(self, results: Dict[str, Dict]):
        """更新性能历史记录"""
        timestamp = datetime.now()
        
        for key, result in results.items():
            if key not in self.performance_history:
                self.performance_history[key] = []
            
            if result['status'] == 'success':
                quality = result.get('quality_metrics', {}).get('overall_quality', 0)
                self.performance_history[key].append({
                    'timestamp': timestamp,
                    'quality': quality,
                    'status': 'success'
                })
                
                # 清理旧记录（保留最近30天）
                cutoff_time = timestamp - timedelta(days=30)
                self.performance_history[key] = [
                    record for record in self.performance_history[key]
                    if record['timestamp'] > cutoff_time
                ]
                
                # 重置失败计数
                if key in self.failure_counts:
                    self.failure_counts[key] = 0
                    
            elif result['status'] == 'failed':
                # 更新失败计数
                if key not in self.failure_counts:
                    self.failure_counts[key] = 0
                self.failure_counts[key] += 1
    
    def track_quality_change(self, key: str, current_quality: float):
        """追踪质量变化"""
        if key not in self.performance_history:
            return
        
        # 获取最近的质量记录
        recent_records = self.performance_history[key][-5:]  # 最近5次记录
        if len(recent_records) < 2:
            return
        
        # 计算质量变化趋势
        qualities = [r['quality'] for r in recent_records]
        quality_trend = np.polyfit(range(len(qualities)), qualities, 1)[0]
        
        # 检查性能下降
        if quality_trend < -self.monitoring_config['performance_degradation_threshold']:
            logger.warning(f"检测到性能下降趋势 {key}: 斜率={quality_trend:.4f}")
            
            # 触发自动重训练
            symbol, timeframe = key.split('-')
            self.trigger_immediate_retraining(symbol, timeframe)
    
    def check_quality_alerts(self, results: Dict[str, Dict]):
        """检查质量告警"""
        low_quality_models = []
        failed_models = []
        
        for key, result in results.items():
            if result['status'] == 'success':
                quality = result.get('quality_metrics', {}).get('overall_quality', 0)
                if quality < self.monitoring_config['quality_threshold']:
                    low_quality_models.append((key, quality))
                    
            elif result['status'] == 'failed':
                failed_models.append(key)
        
        # 生成告警信息
        if low_quality_models:
            alert_msg = "低质量模型告警:\n"
            for key, quality in low_quality_models:
                alert_msg += f"- {key}: 质量评分={quality:.3f}\n"
            logger.warning(alert_msg)
        
        if failed_models:
            alert_msg = "训练失败告警:\n"
            for key in failed_models:
                failure_count = self.failure_counts.get(key, 0)
                alert_msg += f"- {key}: 连续失败次数={failure_count}\n"
                
                # 检查是否需要强制重训练
                if failure_count >= self.monitoring_config['max_consecutive_failures']:
                    symbol, timeframe = key.split('-')
                    self.trigger_emergency_retraining(symbol, timeframe)
            
            logger.error(alert_msg)
    
    def trigger_immediate_retraining(self, symbol: str, timeframe: str):
        """触发立即重训练"""
        logger.info(f"触发立即重训练: {symbol}-{timeframe}")
        
        try:
            result = self.trainer.auto_train_model(symbol, timeframe, force_retrain=True)
            if result['status'] == 'success':
                logger.info(f"立即重训练成功: {symbol}-{timeframe}")
            else:
                logger.error(f"立即重训练失败: {symbol}-{timeframe}")
        except Exception as e:
            logger.error(f"立即重训练异常: {symbol}-{timeframe}, {e}")
    
    def trigger_emergency_retraining(self, symbol: str, timeframe: str):
        """触发紧急重训练"""
        logger.warning(f"触发紧急重训练: {symbol}-{timeframe}")
        
        try:
            # 使用更保守的参数进行紧急重训练
            original_config = self.trainer.param_config.copy()
            self.trainer.param_config['n_components_range'] = [2]  # 只使用2个状态
            self.trainer.param_config['covariance_types'] = ['diag']  # 只使用对角协方差
            
            result = self.trainer.auto_train_model(symbol, timeframe, force_retrain=True)
            
            # 恢复原始配置
            self.trainer.param_config = original_config
            
            if result['status'] == 'success':
                logger.info(f"紧急重训练成功: {symbol}-{timeframe}")
                # 重置失败计数
                key = f"{symbol}-{timeframe}"
                self.failure_counts[key] = 0
            else:
                logger.error(f"紧急重训练失败: {symbol}-{timeframe}")
        except Exception as e:
            logger.error(f"紧急重训练异常: {symbol}-{timeframe}, {e}")
    
    def check_system_resources(self) -> Dict[str, Any]:
        """检查系统资源"""
        try:
            import psutil
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'status': 'healthy'
            }
        except ImportError:
            return {
                'status': 'unknown',
                'message': 'psutil not available'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def generate_quality_report(self, quality_results: Dict[str, Dict]):
        """生成质量报告"""
        try:
            report_file = os.path.join(self.trainer.model_dir, 
                                     f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("# HMM模型质量检查报告\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # 统计信息
                total_models = len(quality_results)
                healthy_models = sum(1 for q in quality_results.values() 
                                    if q.get('overall_quality', 0) >= self.monitoring_config['quality_threshold'])
                
                f.write("## 统计概览\n")
                f.write(f"- 总模型数: {total_models}\n")
                f.write(f"- 健康模型数: {healthy_models}\n")
                f.write(f"- 健康率: {healthy_models/total_models*100:.1f}%\n\n")
                
                # 详细质量信息
                f.write("## 详细质量信息\n")
                for key, metrics in quality_results.items():
                    quality = metrics.get('overall_quality', 0)
                    status = "✅ 健康" if quality >= self.monitoring_config['quality_threshold'] else "⚠️ 警告"
                    f.write(f"- {key}: {status} (质量={quality:.3f})\n")
            
            logger.info(f"质量报告已生成: {report_file}")
            
        except Exception as e:
            logger.error(f"生成质量报告失败: {e}")
    
    def generate_monitoring_report(self, monitoring_results: Dict[str, Dict]):
        """生成监控报告"""
        try:
            report_file = os.path.join(self.trainer.model_dir, 
                                     f"monitoring_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("# HMM系统监控报告\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # 模型文件状态
                f.write("## 模型文件状态\n")
                for model_file, info in monitoring_results.items():
                    if model_file != 'system':
                        f.write(f"- {model_file}: {info.get('status', 'unknown')} ")
                        f.write(f"(年龄: {info.get('file_age_hours', 0):.1f}小时)\n")
                
                # 系统状态
                f.write("\n## 系统状态\n")
                system_info = monitoring_results.get('system', {})
                f.write(f"- CPU使用率: {system_info.get('cpu_percent', 'N/A')}%\n")
                f.write(f"- 内存使用率: {system_info.get('memory_percent', 'N/A')}%\n")
                f.write(f"- 磁盘使用率: {system_info.get('disk_usage', 'N/A')}%\n")
                f.write(f"- 系统状态: {system_info.get('status', 'unknown')}\n")
            
            logger.info(f"监控报告已生成: {report_file}")
            
        except Exception as e:
            logger.error(f"生成监控报告失败: {e}")
    
    def generate_comprehensive_report(self):
        """生成综合报告"""
        try:
            report_file = os.path.join(self.trainer.model_dir, 
                                     f"comprehensive_report_{datetime.now().strftime('%Y%m%d')}.md")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("# HMM模型自动训练系统综合报告\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # 性能历史分析
                f.write("## 性能历史分析\n")
                for key, history in self.performance_history.items():
                    if len(history) > 0:
                        recent_quality = history[-1]['quality']
                        f.write(f"- {key}: 最新质量={recent_quality:.3f}, ")
                        f.write(f"历史记录数={len(history)}\n")
                
                # 失败统计
                f.write("\n## 失败统计\n")
                for key, count in self.failure_counts.items():
                    if count > 0:
                        f.write(f"- {key}: 连续失败次数={count}\n")
                
                # 系统建议
                f.write("\n## 系统建议\n")
                if len(self.failure_counts) > 0:
                    f.write("- 存在连续训练失败的模型，建议检查数据源和网络连接\n")
                if len(self.performance_history) == 0:
                    f.write("- 暂无性能历史数据，建议运行完整训练周期\n")
            
            logger.info(f"综合报告已生成: {report_file}")
            
        except Exception as e:
            logger.error(f"生成综合报告失败: {e}")
    
    def handle_training_failure(self, job_name: str, error: Exception):
        """处理训练失败"""
        logger.error(f"{job_name} 任务失败: {error}")
        
        # 记录失败日志
        error_log_file = os.path.join(self.trainer.model_dir, "error_log.txt")
        with open(error_log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ")
            f.write(f"{job_name} failed: {error}\n")
    
    def setup_schedule(self):
        """设置定时任务"""
        # 每日训练任务
        schedule.every().day.at(self.schedule_config['daily_training_time']).do(
            self.daily_training_job
        )
        
        # 质量检查任务
        schedule.every(self.schedule_config['quality_check_interval_hours']).hours.do(
            self.quality_check_job
        )
        
        # 性能监控任务
        schedule.every(self.schedule_config['performance_monitoring_interval_hours']).hours.do(
            self.performance_monitoring_job
        )
        
        # 报告生成任务
        schedule.every().day.at(self.schedule_config['report_generation_time']).do(
            self.report_generation_job
        )
        
        logger.info("定时任务设置完成")
    
    def run_scheduler(self):
        """运行调度器"""
        self.is_running = True
        
        # 设置定时任务
        self.setup_schedule()
        
        logger.info("HMM自动训练调度器启动...")
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
                
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在停止调度器...")
        except Exception as e:
            logger.error(f"调度器运行异常: {e}")
        finally:
            self.is_running = False
            logger.info("调度器已停止")
    
    def start(self):
        """启动调度器（后台线程）"""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("调度器已在运行中")
            return
        
        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("调度器后台线程已启动")
    
    def stop(self):
        """停止调度器"""
        self.is_running = False
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=30)
            
        logger.info("调度器已停止")


def main():
    """主函数 - 启动自动调度器"""
    scheduler = HMMAutoScheduler()
    
    try:
        # 启动调度器
        scheduler.start()
        
        # 保持主线程运行
        while scheduler.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    finally:
        scheduler.stop()


if __name__ == "__main__":
    main()