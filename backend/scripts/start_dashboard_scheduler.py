#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard物化视图刷新调度器启动脚本

功能：启动物化视图刷新调度器，每15分钟自动刷新物化视图

作者: AI Assistant
创建时间: 2025-01-14
"""

import os
import sys
import signal
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scheduler.dashboard_materialized_view_scheduler import DashboardMaterializedViewScheduler
from common.logger import LoggerFactory

logger = LoggerFactory.get_logger("dashboard_scheduler_runner")

class DashboardSchedulerRunner:
    """Dashboard调度器运行器"""
    
    def __init__(self):
        self.scheduler = DashboardMaterializedViewScheduler()
        self.is_running = False
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，正在停止调度器...")
        self.stop()
    
    def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("调度器已经在运行中")
            return
        
        logger.info("启动Dashboard物化视图刷新调度器...")
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # 启动调度器
            self.scheduler.start()
            self.is_running = True
            
            logger.info("Dashboard物化视图刷新调度器启动成功")
            logger.info("调度器将每15分钟自动刷新物化视图")
            
            # 保持主线程运行
            while self.is_running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号，正在停止调度器...")
            self.stop()
        except Exception as e:
            logger.error(f"调度器运行异常: {e}")
            self.stop()
    
    def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        logger.info("正在停止Dashboard物化视图刷新调度器...")
        
        try:
            self.scheduler.stop()
            self.is_running = False
            logger.info("Dashboard物化视图刷新调度器已停止")
        except Exception as e:
            logger.error(f"停止调度器时发生错误: {e}")

def main():
    """主函数"""
    print("=== Dashboard物化视图刷新调度器 ===")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("调度间隔: 每15分钟")
    print("刷新视图: dashboard_market_sentiment, dashboard_strong_weak_coins, dashboard_coin_analysis, dashboard_summary_view")
    print("=" * 50)
    
    runner = DashboardSchedulerRunner()
    runner.start()

if __name__ == "__main__":
    main()