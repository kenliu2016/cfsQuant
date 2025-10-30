#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard物化视图刷新调度器

功能特性：
1. 每15分钟自动刷新所有dashboard物化视图
2. 支持并发刷新，提高性能
3. 错误处理和重试机制
4. 性能监控和日志记录

作者: AI Assistant
创建时间: 2025-01-14
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

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.logger import LoggerFactory
from common.db import get_engine, execute

logger = LoggerFactory.get_logger("scheduler.dashboard_materialized_view")

class DashboardMaterializedViewScheduler:
    """Dashboard物化视图刷新调度器"""
    
    def __init__(self):
        self.engine = get_engine()
        self.is_running = False
        self.scheduler_thread = None
        
        # 调度配置
        self.schedule_config = {
            'refresh_interval_minutes': 15,  # 刷新间隔（分钟）
            'max_retry_attempts': 3,  # 最大重试次数
            'retry_delay_seconds': 30,  # 重试延迟（秒）
        }
        
        # 物化视图列表
        self.materialized_views = [
            'dashboard_market_sentiment',
            'dashboard_strong_weak_coins', 
            'dashboard_coin_analysis',
            'dashboard_summary_view'
        ]
        
        # 性能追踪数据
        self.performance_history = {}
        self.failure_counts = {}
    
    def refresh_materialized_view(self, view_name: str) -> bool:
        """
        刷新单个物化视图
        
        Args:
            view_name: 物化视图名称
            
        Returns:
            刷新是否成功
        """
        start_time = datetime.now()
        
        try:
            # 先尝试并发刷新（适用于有唯一索引的物化视图）
            refresh_sql = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"
            
            logger.info(f"开始并发刷新物化视图: {view_name}")
            
            # 执行刷新操作
            with self.engine.connect() as conn:
                from sqlalchemy import text
                result = conn.execute(text(refresh_sql))
                conn.commit()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"物化视图并发刷新成功: {view_name}, 耗时: {execution_time:.2f}秒")
            
            # 更新性能历史
            self.update_performance_history(view_name, True, execution_time)
            
            return True
            
        except Exception as e:
            # 如果并发刷新失败，回退到普通刷新
            logger.warning(f"物化视图并发刷新失败: {view_name}, 错误: {e}, 尝试普通刷新")
            
            try:
                # 使用普通刷新（无CONCURRENTLY选项）
                refresh_sql = f"REFRESH MATERIALIZED VIEW {view_name}"
                
                logger.info(f"开始普通刷新物化视图: {view_name}")
                
                with self.engine.connect() as conn:
                    from sqlalchemy import text
                    result = conn.execute(text(refresh_sql))
                    conn.commit()
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                logger.info(f"物化视图普通刷新成功: {view_name}, 耗时: {execution_time:.2f}秒")
                
                # 更新性能历史
                self.update_performance_history(view_name, True, execution_time)
                
                return True
                
            except Exception as fallback_error:
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(f"物化视图刷新失败: {view_name}, 错误: {fallback_error}, 耗时: {execution_time:.2f}秒")
                
                # 更新性能历史
                self.update_performance_history(view_name, False, execution_time)
                
                return False
    
    def refresh_all_views_with_retry(self) -> Dict[str, bool]:
        """
        刷新所有物化视图（带重试机制）
        
        Returns:
            各视图刷新结果字典
        """
        results = {}
        
        for view_name in self.materialized_views:
            success = False
            
            for attempt in range(self.schedule_config['max_retry_attempts']):
                if attempt > 0:
                    logger.info(f"第{attempt + 1}次尝试刷新物化视图: {view_name}")
                    time.sleep(self.schedule_config['retry_delay_seconds'])
                
                success = self.refresh_materialized_view(view_name)
                
                if success:
                    break
            
            results[view_name] = success
        
        return results
    
    def refresh_all_dashboard_views(self):
        """刷新所有dashboard物化视图的主任务"""
        logger.info("开始执行Dashboard物化视图刷新任务...")
        
        start_time = datetime.now()
        
        try:
            # 刷新所有物化视图
            results = self.refresh_all_views_with_retry()
            
            # 统计结果
            successful_refreshes = sum(1 for success in results.values() if success)
            total_views = len(results)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            if successful_refreshes == total_views:
                logger.info(f"所有物化视图刷新成功! 总计耗时: {execution_time:.2f}秒")
            else:
                failed_views = [view for view, success in results.items() if not success]
                logger.warning(f"部分物化视图刷新失败: {failed_views}, 成功: {successful_refreshes}/{total_views}, 耗时: {execution_time:.2f}秒")
            
            # 生成性能报告
            self.generate_performance_report()
            
        except Exception as e:
            logger.error(f"Dashboard物化视图刷新任务执行失败: {e}")
    
    def update_performance_history(self, view_name: str, success: bool, execution_time: float):
        """更新性能历史数据"""
        if view_name not in self.performance_history:
            self.performance_history[view_name] = {
                'success_count': 0,
                'failure_count': 0,
                'total_execution_time': 0.0,
                'last_execution_time': execution_time,
                'last_success': success,
                'last_execution': datetime.now()
            }
        
        history = self.performance_history[view_name]
        
        if success:
            history['success_count'] += 1
        else:
            history['failure_count'] += 1
            
            # 更新失败计数
            if view_name not in self.failure_counts:
                self.failure_counts[view_name] = 0
            self.failure_counts[view_name] += 1
        
        history['total_execution_time'] += execution_time
        history['last_execution_time'] = execution_time
        history['last_success'] = success
        history['last_execution'] = datetime.now()
    
    def generate_performance_report(self):
        """生成性能报告"""
        if not self.performance_history:
            return
        
        logger.info("=== Dashboard物化视图性能报告 ===")
        
        for view_name, history in self.performance_history.items():
            total_attempts = history['success_count'] + history['failure_count']
            success_rate = (history['success_count'] / total_attempts * 100) if total_attempts > 0 else 0
            avg_execution_time = history['total_execution_time'] / total_attempts if total_attempts > 0 else 0
            
            logger.info(f"视图: {view_name}")
            logger.info(f"  成功率: {success_rate:.1f}% ({history['success_count']}/{total_attempts})")
            logger.info(f"  平均执行时间: {avg_execution_time:.2f}秒")
            logger.info(f"  最后执行: {history['last_execution'].strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  最后状态: {'成功' if history['last_success'] else '失败'}")
        
        logger.info("================================")
    
    def check_health_status(self) -> Dict[str, Any]:
        """检查调度器健康状态"""
        health_status = {
            'is_running': self.is_running,
            'last_check': datetime.now(),
            'views_status': {}
        }
        
        for view_name in self.materialized_views:
            if view_name in self.performance_history:
                history = self.performance_history[view_name]
                total_attempts = history['success_count'] + history['failure_count']
                success_rate = (history['success_count'] / total_attempts * 100) if total_attempts > 0 else 0
                
                health_status['views_status'][view_name] = {
                    'success_rate': success_rate,
                    'last_execution': history['last_execution'],
                    'last_status': 'healthy' if history['last_success'] else 'unhealthy',
                    'consecutive_failures': self.failure_counts.get(view_name, 0)
                }
            else:
                health_status['views_status'][view_name] = {
                    'success_rate': 0,
                    'last_execution': None,
                    'last_status': 'unknown',
                    'consecutive_failures': 0
                }
        
        return health_status
    
    def setup_schedule(self):
        """设置定时任务"""
        # 每15分钟执行一次刷新任务
        schedule.every(self.schedule_config['refresh_interval_minutes']).minutes.do(
            self.refresh_all_dashboard_views
        )
        
        logger.info(f"定时任务设置完成，每{self.schedule_config['refresh_interval_minutes']}分钟刷新一次物化视图")
    
    def run_scheduler(self):
        """运行调度器"""
        self.is_running = True
        
        # 设置定时任务
        self.setup_schedule()
        
        logger.info("Dashboard物化视图刷新调度器启动...")
        
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
    """主函数 - 启动调度器"""
    scheduler = DashboardMaterializedViewScheduler()
    
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