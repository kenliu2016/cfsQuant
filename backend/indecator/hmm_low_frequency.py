#!/usr/bin/env python3
"""
低频周期HMM执行脚本
执行周期：每天凌晨1点
分析周期：1天, 2天, 3天, 3个月
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger import LoggerFactory

logger = LoggerFactory.get_logger("indecator.hmm_low_frequency")

def main():
    """低频周期HMM分析主函数"""
    logger.info("开始执行低频周期HMM分析")
    
    try:
        # 导入并执行HMM分析
        from hmm_schedule import run_hmm_for_period
        run_hmm_for_period('low_frequency')
        
        logger.info("低频周期HMM分析执行完成")
    except Exception as e:
        logger.error(f"低频周期HMM分析执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()