#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HMM模型全自动训练和参数优化系统

集成模块：
1. 自动训练器 (hmm_auto_trainer)
2. 调度器 (hmm_auto_scheduler) 
3. 质量管理器 (hmm_quality_manager)
4. 监控系统 (hmm_monitoring_system)

功能特性：
- 全自动数据获取和预处理
- 智能参数优化和模型选择
- 自动质量评估和重训练
- 定时调度和性能监控
- 异常告警和自动恢复
"""

import os
import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, backend_dir)
sys.path.insert(0, current_dir)
from common.logger import LoggerFactory
from hmm_auto_trainer import HMMAutoTrainer
from hmm_auto_scheduler import HMMAutoScheduler
from hmm_quality_manager import HMMQualityManager, ModelQualityStatus

logger = LoggerFactory.get_logger("hmm_full_auto_system")

class HMMFullAutoSystem:
    """HMM模型全自动训练系统"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化全自动系统
        
        Args:
            config_file: 配置文件路径
        """
        # 加载配置
        self.config = self._load_config(config_file)
        
        # 初始化各个模块，使用配置中的模型保存目录
        self.trainer = HMMAutoTrainer(model_dir=self.config['model_save_dir'])
        self.scheduler = HMMAutoScheduler()
        self.quality_manager = HMMQualityManager()
        
        # 系统状态
        self.is_running = False
        self.system_thread = None
        self.emergency_mode = False
        
        # 性能统计
        self.performance_stats = {
            'total_trainings': 0,
            'successful_trainings': 0,
            'failed_trainings': 0,
            'last_training_time': None,
            'average_training_duration': 0,
            'system_uptime': 0
        }
        
        logger.info("HMM全自动训练系统初始化完成")
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典，包含系统运行参数
        """
        default_config = {
            'auto_start': True,
            'monitoring_interval_minutes': 5,
            'emergency_retry_interval_minutes': 1,
            'max_emergency_retries': 10,
            'performance_report_interval_hours': 24,
            'quality_alert_threshold': 0.6,
            'performance_degradation_threshold': -0.02,
            'timeframes': ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '2d', '3d'],
            'model_save_dir': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'hmmModel')
        }
        
        # 动态获取symbol列表
        default_config['symbols'] = self._get_active_usdt_symbols()
        
        # TODO: 从配置文件加载配置
        return default_config
    
    def _get_active_usdt_symbols(self) -> List[str]:
        """
        从market_codes表获取活跃的USDT交易对
        
        Returns:
            活跃的USDT交易对列表，格式为['BTC/USDT', 'ETH/USDT', ...]
        """
        try:
            from common.db import get_engine
            import pandas as pd
            
            engine = get_engine()
            sql = """
            SELECT symbol, exchange, basecurrency, quotecurrency 
            FROM market_codes 
            WHERE active = true 
            AND quotecurrency = 'USDT'
            ORDER BY symbol
            """
            
            df = pd.read_sql(sql, engine)
            
            # 转换为标准格式：BASE/USDT
            symbols = []
            for _, row in df.iterrows():
                if row['basecurrency']:
                    symbol = f"{row['basecurrency']}/USDT"
                    symbols.append(symbol)
            
            logger.info(f"从数据库获取到 {len(symbols)} 个活跃USDT交易对")
            if symbols:
                logger.info(f"交易对列表: {symbols[:5]}{'...' if len(symbols) > 5 else ''}")
            
            return symbols
            
        except Exception as e:
            logger.error(f"获取活跃USDT交易对失败: {e}")
            # 返回默认的交易对列表作为备选
            return ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']
    
    def start_system(self):
        """启动全自动系统"""
        if self.is_running:
            logger.warning("系统已在运行中")
            return
        
        self.is_running = True
        self.system_start_time = datetime.now()
        
        # 启动调度器
        self.scheduler.start()
        
        # 启动系统监控线程
        self.system_thread = threading.Thread(target=self._system_monitor_loop, daemon=True)
        self.system_thread.start()
        
        # 执行初始训练
        self._initial_training()
        
        logger.info("HMM全自动训练系统启动完成")
    
    def stop_system(self):
        """停止全自动系统"""
        if not self.is_running:
            logger.warning("系统未在运行中")
            return
        
        self.is_running = False
        
        # 停止调度器
        self.scheduler.stop()
        
        # 等待系统线程结束
        if self.system_thread:
            self.system_thread.join(timeout=30)
        
        # 更新运行时间统计
        if hasattr(self, 'system_start_time'):
            self.performance_stats['system_uptime'] = (
                datetime.now() - self.system_start_time
            ).total_seconds()
        
        logger.info("HMM全自动训练系统已停止")
    
    def _system_monitor_loop(self):
        """系统监控循环"""
        last_performance_report = datetime.now()
        emergency_retry_count = 0
        
        while self.is_running:
            try:
                # 检查系统健康状况
                system_health = self._check_system_health()
                
                if not system_health['overall_health']:
                    logger.warning("系统健康检查失败，进入紧急模式")
                    self.emergency_mode = True
                    
                    # 执行紧急恢复
                    if self._emergency_recovery():
                        emergency_retry_count = 0
                        self.emergency_mode = False
                        logger.info("紧急恢复成功，退出紧急模式")
                    else:
                        emergency_retry_count += 1
                        
                        if emergency_retry_count >= self.config['max_emergency_retries']:
                            logger.error("紧急恢复失败次数过多，系统停止")
                            self.stop_system()
                            break
                else:
                    self.emergency_mode = False
                    emergency_retry_count = 0
                
                # 性能退化检测
                self._detect_performance_degradation()
                
                # 定期生成性能报告
                current_time = datetime.now()
                hours_since_last_report = (
                    current_time - last_performance_report
                ).total_seconds() / 3600
                
                if hours_since_last_report >= self.config['performance_report_interval_hours']:
                    self._generate_performance_report()
                    last_performance_report = current_time
                
                # 休眠等待下次检查
                time.sleep(self.config['monitoring_interval_minutes'] * 60)
                
            except Exception as e:
                logger.error(f"系统监控循环异常: {e}")
                time.sleep(60)  # 异常后等待1分钟
    
    def _check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状况"""
        health_checks = {}
        
        try:
            # 检查数据库连接
            from common.db import get_engine
            engine = get_engine()
            with engine.begin() as conn:
                conn.execute("SELECT 1")
            health_checks['database'] = True
        except Exception as e:
            logger.error(f"数据库连接检查失败: {e}")
            health_checks['database'] = False
        
        try:
            # 检查模型目录
            model_files = [f for f in os.listdir(self.trainer.model_dir) 
                          if f.endswith('.pkl')]
            health_checks['model_files'] = len(model_files) > 0
        except Exception as e:
            logger.error(f"模型文件检查失败: {e}")
            health_checks['model_files'] = False
        
        try:
            # 检查调度器状态
            health_checks['scheduler'] = self.scheduler.is_running
        except Exception as e:
            logger.error(f"调度器状态检查失败: {e}")
            health_checks['scheduler'] = False
        
        # 总体健康状态
        overall_health = all(health_checks.values())
        
        return {
            'overall_health': overall_health,
            'health_checks': health_checks
        }
    
    def _emergency_recovery(self) -> bool:
        """紧急恢复"""
        logger.info("开始执行紧急恢复...")
        
        recovery_success = True
        
        try:
            # 1. 重启调度器
            self.scheduler.stop()
            time.sleep(5)
            self.scheduler.start()
            
            # 2. 执行基础训练，使用配置中的前几个symbols和timeframes
            basic_symbols = self.config['symbols'][:2] if len(self.config['symbols']) >= 2 else self.config['symbols']
            basic_timeframes = self.config['timeframes'][:1] if len(self.config['timeframes']) >= 1 else self.config['timeframes']
            
            logger.info(f"紧急恢复训练配置: {len(basic_symbols)}个交易对, {len(basic_timeframes)}个时间周期")
            
            for symbol in basic_symbols:
                for timeframe in basic_timeframes:
                    result = self.trainer.auto_train_model(symbol, timeframe, force_retrain=True)
                    if result['status'] != 'success':
                        recovery_success = False
                        logger.error(f"紧急训练失败: {symbol}-{timeframe}")
            
            if recovery_success:
                logger.info("紧急恢复完成")
            else:
                logger.error("紧急恢复部分失败")
                
        except Exception as e:
            logger.error(f"紧急恢复异常: {e}")
            recovery_success = False
        
        return recovery_success
    
    def _initial_training(self):
        """执行初始训练"""
        logger.info("开始执行初始训练...")
        
        # 使用配置中的symbols和timeframes
        symbols = self.config['symbols']
        timeframes = self.config['timeframes']
        
        logger.info(f"初始训练配置: {len(symbols)}个交易对, {len(timeframes)}个时间周期")
        logger.info(f"交易对列表: {symbols}")
        logger.info(f"时间周期列表: {timeframes}")
        
        # 执行批量训练
        results = self.trainer.batch_train_models(symbols, timeframes)
        
        # 更新性能统计
        self._update_performance_stats(results)
        
        logger.info("初始训练完成")
    
    def _detect_performance_degradation(self):
        """检测性能退化"""
        try:
            symbols = self.config['symbols']
            timeframes = self.config['timeframes']
            
            degradation_detected = False
            
            for symbol in symbols:
                for timeframe in timeframes:
                    if self.quality_manager.detect_performance_degradation(symbol, timeframe):
                        logger.warning(f"检测到性能退化: {symbol}-{timeframe}")
                        degradation_detected = True
                        
                        # 触发优化重训练
                        self._trigger_optimized_retraining(symbol, timeframe)
            
            if not degradation_detected:
                logger.debug("未检测到性能退化")
                
        except Exception as e:
            logger.error(f"性能退化检测失败: {e}")
    
    def _trigger_optimized_retraining(self, symbol: str, timeframe: str):
        """触发优化重训练"""
        logger.info(f"触发优化重训练: {symbol}-{timeframe}")
        
        try:
            # 获取当前质量评估
            df_returns = self.trainer.get_training_data(symbol, timeframe, lookback_days=1)
            if df_returns is None:
                logger.warning(f"无法获取数据，跳过优化重训练: {symbol}-{timeframe}")
                return
            
            assessment = self.quality_manager.comprehensive_quality_assessment(
                symbol, timeframe, df_returns
            )
            
            # 根据评估结果调整训练策略
            if assessment.quality_status in [ModelQualityStatus.POOR, ModelQualityStatus.FAILED]:
                # 使用保守参数
                original_config = self.trainer.param_config.copy()
                self.trainer.param_config['n_components_range'] = [2, 3]
                self.trainer.param_config['covariance_types'] = ['diag', 'full']
                
                result = self.trainer.auto_train_model(symbol, timeframe, force_retrain=True)
                
                # 恢复原始配置
                self.trainer.param_config = original_config
                
            else:
                # 正常优化训练
                result = self.trainer.auto_train_model(symbol, timeframe, force_retrain=True)
            
            if result['status'] == 'success':
                logger.info(f"优化重训练成功: {symbol}-{timeframe}")
            else:
                logger.error(f"优化重训练失败: {symbol}-{timeframe}")
                
        except Exception as e:
            logger.error(f"优化重训练异常: {symbol}-{timeframe}, {e}")
    
    def _update_performance_stats(self, results: Dict[str, Dict]):
        """更新性能统计"""
        self.performance_stats['total_trainings'] += len(results)
        self.performance_stats['successful_trainings'] += sum(
            1 for r in results.values() if r['status'] == 'success'
        )
        self.performance_stats['failed_trainings'] += sum(
            1 for r in results.values() if r['status'] == 'failed'
        )
        self.performance_stats['last_training_time'] = datetime.now()
    
    def _generate_performance_report(self):
        """生成性能报告"""
        try:
            report_file = os.path.join(self.trainer.model_dir, 
                                     f"system_performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("# HMM全自动训练系统性能报告\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # 系统概览
                f.write("## 系统概览\n")
                f.write(f"- 系统运行时间: {self.performance_stats.get('system_uptime', 0):.1f} 秒\n")
                f.write(f"- 紧急模式: {'是' if self.emergency_mode else '否'}\n")
                f.write(f"- 调度器状态: {'运行中' if self.scheduler.is_running else '停止'}\n\n")
                
                # 训练统计
                f.write("## 训练统计\n")
                total = self.performance_stats['total_trainings']
                success = self.performance_stats['successful_trainings']
                failed = self.performance_stats['failed_trainings']
                
                if total > 0:
                    success_rate = success / total * 100
                    f.write(f"- 总训练次数: {total}\n")
                    f.write(f"- 成功次数: {success} ({success_rate:.1f}%)\n")
                    f.write(f"- 失败次数: {failed}\n")
                    f.write(f"- 最后训练时间: {self.performance_stats.get('last_training_time', 'N/A')}\n\n")
                
                # 质量评估统计
                f.write("## 质量评估统计\n")
                quality_report = self.quality_manager.generate_quality_report()
                if quality_report:
                    f.write(f"- 质量报告: {quality_report}\n")
                
                # 系统建议
                f.write("\n## 系统建议\n")
                if self.emergency_mode:
                    f.write("- ⚠️ 系统处于紧急模式，建议检查系统状态\n")
                if failed > success * 0.1:  # 失败率超过10%
                    f.write("- ⚠️ 训练失败率较高，建议检查数据源\n")
                if total == 0:
                    f.write("- ℹ️ 暂无训练记录，建议执行初始训练\n")
                
                f.write("- ✅ 系统运行正常\n")
            
            logger.info(f"性能报告已生成: {report_file}")
            
        except Exception as e:
            logger.error(f"生成性能报告失败: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        health_check = self._check_system_health()
        
        return {
            'is_running': self.is_running,
            'emergency_mode': self.emergency_mode,
            'scheduler_running': self.scheduler.is_running,
            'system_health': health_check,
            'performance_stats': self.performance_stats,
            'uptime_seconds': self.performance_stats.get('system_uptime', 0)
        }
    
    def manual_training(self, symbols: List[str], timeframes: List[str]):
        """手动执行训练"""
        logger.info(f"手动执行训练: symbols={symbols}, timeframes={timeframes}")
        
        results = self.trainer.batch_train_models(symbols, timeframes)
        self._update_performance_stats(results)
        
        return results
    
    def force_retraining(self, symbol: str, timeframe: str):
        """强制重训练指定模型"""
        logger.info(f"强制重训练: {symbol}-{timeframe}")
        
        result = self.trainer.auto_train_model(symbol, timeframe, force_retrain=True)
        
        if result['status'] == 'success':
            logger.info(f"强制重训练成功: {symbol}-{timeframe}")
        else:
            logger.error(f"强制重训练失败: {symbol}-{timeframe}")
        
        return result


def main():
    """主函数 - 启动全自动系统"""
    system = HMMFullAutoSystem()
    
    try:
        # 启动系统
        system.start_system()
        
        print("HMM全自动训练系统已启动")
        print("输入 'status' 查看系统状态")
        print("输入 'stop' 停止系统")
        print("输入 'exit' 退出程序")
        
        # 简单的命令行交互
        while system.is_running:
            try:
                command = input("\n请输入命令: ").strip().lower()
                
                if command == 'status':
                    status = system.get_system_status()
                    print(f"系统状态: {'运行中' if status['is_running'] else '停止'}")
                    print(f"紧急模式: {'是' if status['emergency_mode'] else '否'}")
                    print(f"调度器状态: {'运行中' if status['scheduler_running'] else '停止'}")
                    print(f"系统运行时间: {status['uptime_seconds']:.0f} 秒")
                    
                elif command == 'stop':
                    system.stop_system()
                    print("系统正在停止...")
                    
                elif command == 'exit':
                    system.stop_system()
                    break
                    
                elif command.startswith('train'):
                    # 简单的手动训练命令: train BTC/USDT,ETH/USDT 1h,4h
                    parts = command.split()
                    if len(parts) >= 3:
                        symbols = [s.strip() for s in parts[1].split(',')]
                        timeframes = [t.strip() for t in parts[2].split(',')]
                        results = system.manual_training(symbols, timeframes)
                        print(f"手动训练完成: 成功 {sum(1 for r in results.values() if r['status']=='success')}/{len(results)}")
                    else:
                        print("用法: train 符号列表 时间周期列表")
                        print("示例: train BTC/USDT,ETH/USDT 1h,4h")
                        
                elif command.startswith('force'):
                    # 强制重训练命令: force BTC/USDT 1h
                    parts = command.split()
                    if len(parts) >= 3:
                        symbol = parts[1]
                        timeframe = parts[2]
                        result = system.force_retraining(symbol, timeframe)
                        print(f"强制重训练结果: {result['status']}")
                    else:
                        print("用法: force 符号 时间周期")
                        print("示例: force BTC/USDT 1h")
                        
                else:
                    print("未知命令，可用命令: status, stop, exit, train, force")
                    
            except KeyboardInterrupt:
                print("\n收到中断信号")
                system.stop_system()
                break
            except Exception as e:
                print(f"命令执行错误: {e}")
        
        print("程序退出")
        
    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        system.stop_system()


if __name__ == "__main__":
    main()